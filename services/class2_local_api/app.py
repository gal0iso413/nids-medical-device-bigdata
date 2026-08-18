"""FastAPI application factory for the localhost-only Class 2 query API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import re

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .reader import MartReader, QueryContractError
from .schemas import ComparisonRequest


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


def _validate_static_root(static_root: Path, mart_root: Path) -> Path:
    root = Path(static_root)
    if not root.is_dir() or not (root / "index.html").is_file():
        raise StaticRootError("static root must be a directory containing index.html")
    resolved = root.resolve()
    if _inside(resolved, mart_root) or _inside(mart_root, resolved):
        raise StaticRootError("static root must not overlap the serving mart")
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


def create_app(mart_root: Path) -> FastAPI:
    """Create an app only after synchronously verifying the serving mart."""
    reader = MartReader.open(Path(mart_root))

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            reader.close()

    app = FastAPI(
        title="Class 2 local query API", docs_url=None, redoc_url=None,
        openapi_url=None, lifespan=lifespan,
    )
    app.state.mart_reader = reader

    def bad_request(exc: QueryContractError) -> HTTPException:
        return HTTPException(status_code=422, detail=str(exc))

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok", "mart_fingerprint": reader.mart.fingerprint, "service_mode": "local_internal_only"}

    @app.get("/v1/status")
    def status() -> dict[str, str]:
        return {
            "service_mode": "local_internal_only", "public_release_policy": "not_approved",
            "period_start": reader.mart.period_start, "period_end": reader.mart.period_end,
            "mart_fingerprint": reader.mart.fingerprint,
        }

    @app.get("/v1/catalog/item-groups")
    def item_groups(q: str | None = Query(default=None, max_length=256), limit: int | None = Query(default=None)) -> dict[str, object]:
        try:
            bounded = reader._limit(limit)
            return {"limit": bounded, "items": reader.item_groups(q, bounded)}
        except QueryContractError as exc:
            raise bad_request(exc) from exc

    @app.get("/v1/catalog/item-names")
    def item_names(item_group_id: str = Query(min_length=1, max_length=512), q: str | None = Query(default=None, max_length=256), limit: int | None = Query(default=None)) -> dict[str, object]:
        try:
            bounded = reader._limit(limit)
            return {"limit": bounded, "items": reader.item_names(item_group_id, q, bounded)}
        except QueryContractError as exc:
            raise bad_request(exc) from exc

    @app.post("/v1/comparisons")
    def comparisons(request: ComparisonRequest) -> dict[str, object]:
        try:
            return reader.comparison(request.period_start, request.period_end, request.selections)
        except QueryContractError as exc:
            raise bad_request(exc) from exc

    return app


def create_integrated_app(mart_root: Path, static_root: Path) -> FastAPI:
    """Serve the fixed local API under /api and an audited React build at /."""
    api = create_app(mart_root)
    try:
        root = _validate_static_root(Path(static_root), api.state.mart_reader.mart.root)
    except Exception:
        api.state.mart_reader.close()
        raise
    app = FastAPI(title="Class 2 local integrated host", docs_url=None, redoc_url=None, openapi_url=None)
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
