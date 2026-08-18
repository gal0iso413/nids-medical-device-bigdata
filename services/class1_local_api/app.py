"""FastAPI application factory for the localhost-only Class 1 lookup API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from .reader import (
    IndexReader,
    LookupContractError,
    LookupEntityNotFoundError,
    LookupMonthUnavailableError,
)


class StaticRootError(RuntimeError):
    """Raised before startup when a production static root is unsafe."""


_FORBIDDEN_STATIC_SUFFIXES = frozenset({".parquet", ".xlsx", ".xls", ".sqlite", ".db", ".zip", ".exe", ".whl", ".json"})
_FORBIDDEN_STATIC_NAMES = frozenset({"_manifest.json", "checkpoint.sqlite"})
_RAW_ENDPOINT = re.compile(rb"(?i)(?:co|hosp):[A-Za-z0-9][A-Za-z0-9_.-]*")
_WINDOWS_ABSOLUTE_PATH = re.compile(rb"(?i)(?<![a-z0-9+.-])[a-z]:[\\/]")


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _is_forbidden_static_path(relative: Path) -> bool:
    return (
        relative.name in _FORBIDDEN_STATIC_NAMES
        or relative.suffix.lower() in _FORBIDDEN_STATIC_SUFFIXES
        or "generated" in relative.parts
    )


def _validate_static_root(static_root: Path, index_root: Path) -> Path:
    root = Path(static_root)
    if not root.is_dir() or not (root / "index.html").is_file():
        raise StaticRootError("static root must be a directory containing index.html")
    resolved = root.resolve()
    if _inside(resolved, index_root) or _inside(index_root, resolved):
        raise StaticRootError("static root must not overlap the lookup index")
    for path in root.rglob("*"):
        if not _inside(path, resolved):
            raise StaticRootError("static root contains a path outside its root")
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if _is_forbidden_static_path(relative):
            raise StaticRootError("static root contains a forbidden data artifact")
        if path.suffix.lower() in {".html", ".js", ".css", ".svg", ".txt"}:
            payload = path.read_bytes()
            if _RAW_ENDPOINT.search(payload) or _WINDOWS_ABSOLUTE_PATH.search(payload):
                raise StaticRootError("static root contains private identifiers or an absolute path")
    return resolved


def _http_for_lookup(exc: LookupContractError) -> HTTPException:
    if isinstance(exc, LookupMonthUnavailableError):
        return HTTPException(status_code=422, detail=str(exc))
    if isinstance(exc, LookupEntityNotFoundError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=422, detail=str(exc))


def create_app(index_root: Path) -> FastAPI:
    """Create an app only after synchronously verifying the lookup index."""
    reader = IndexReader.open(Path(index_root))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            reader.close()

    app = FastAPI(
        title="Class 1 local lookup API", docs_url=None, redoc_url=None,
        openapi_url=None, lifespan=lifespan,
    )
    app.state.index_reader = reader

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "index_fingerprint": reader.lookup_catalog.fingerprint,
            "service_mode": "local_internal_only",
        }

    @app.get("/v1/status")
    def status() -> dict[str, object]:
        return reader.status_payload()

    @app.get("/v1/review-queue")
    def review_queue(anchor_month: str | None = None) -> dict[str, object]:
        try:
            return reader.review_queue(anchor_month)
        except LookupContractError as exc:
            raise _http_for_lookup(exc) from exc

    @app.get("/v1/catalog/entities")
    def catalog(q: str = "", limit: int = 20, anchor_month: str | None = None) -> dict[str, object]:
        try:
            return reader.catalog(q, limit, anchor_month)
        except LookupContractError as exc:
            raise _http_for_lookup(exc) from exc

    @app.get("/v1/entities/{entity_id}/relationships")
    def relationships(entity_id: str, anchor_month: str | None = None) -> dict[str, object]:
        try:
            return reader.relationships(entity_id, anchor_month)
        except LookupContractError as exc:
            raise _http_for_lookup(exc) from exc

    @app.get("/v1/entities/{entity_id}")
    def review(entity_id: str, anchor_month: str | None = None) -> dict[str, object]:
        try:
            return reader.review(entity_id, anchor_month)
        except LookupContractError as exc:
            raise _http_for_lookup(exc) from exc

    return app


def create_integrated_app(index_root: Path, static_root: Path) -> FastAPI:
    """Serve the fixed local API under /api and an audited React build at /."""
    api = create_app(index_root)
    try:
        root = _validate_static_root(Path(static_root), api.state.index_reader.index.root)
    except Exception:
        api.state.index_reader.close()
        raise
    app = FastAPI(title="Class 1 local integrated host", docs_url=None, redoc_url=None, openapi_url=None)
    app.mount("/api", api)

    def static_response(asset_path: str = "") -> FileResponse:
        requested = root / asset_path
        if asset_path and _inside(requested, root) and _is_forbidden_static_path(requested.relative_to(root)):
            raise HTTPException(status_code=404)
        if asset_path and _inside(requested, root) and requested.is_file():
            return FileResponse(requested)
        return FileResponse(root / "index.html")

    app.get("/", include_in_schema=False)(static_response)
    app.get("/{asset_path:path}", include_in_schema=False)(static_response)
    return app
