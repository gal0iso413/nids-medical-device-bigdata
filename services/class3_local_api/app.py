"""FastAPI application factory for the localhost-only Class 3 query API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query

from .reader import MartReader, QueryContractError
from .schemas import ComparisonRequest


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
        title="Class 3 local query API", docs_url=None, redoc_url=None,
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
