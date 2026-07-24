from typing import Annotated, Any

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from workers.ingestion.runner import run_sync

from .config import get_settings
from .database import get_session
from .schemas import StatusResponse, SyncRequest, SyncResult
from .security import verify_internal_secret
from .snapshot import find_by_slug, load_snapshot, paginated

settings = get_settings()
logger = structlog.get_logger()
app = FastAPI(
    title="丽泽路1号 Public API",
    version="1.0.0",
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.public_origins,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(Exception)
async def unhandled_error(_request: Any, exc: Exception) -> JSONResponse:
    logger.exception("unhandled_error", error_type=type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/healthz", include_in_schema=False)
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/status", response_model=StatusResponse)
async def status(
    session: Annotated[AsyncSession | None, Depends(get_session)],
) -> StatusResponse:
    snapshot = load_snapshot()
    return StatusResponse(
        status="ok",
        database="connected" if session is not None else "snapshot-fallback",
        snapshot_updated_at=snapshot.get("updated_at"),
    )


@app.get("/api/v1/dashboard")
async def dashboard() -> dict[str, Any]:
    return load_snapshot()


def filtered_page(
    key: str,
    page: int,
    page_size: int,
    q: str | None,
    region: str | None,
    sector: str | None,
) -> dict[str, Any]:
    items = list(load_snapshot().get(key, []))
    if q:
        term = q.casefold()
        items = [item for item in items if term in str(item).casefold()]
    if region:
        items = [item for item in items if item.get("region") == region]
    if sector:
        items = [item for item in items if item.get("sector") == sector]
    return paginated(items, page, page_size)


@app.get("/api/v1/news")
async def news(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=settings.max_page_size),
    q: str | None = None,
    region: str | None = None,
    sector: str | None = None,
) -> dict[str, Any]:
    return filtered_page("events", page, page_size, q, region, sector)


@app.get("/api/v1/news/{item_id}")
async def news_detail(item_id: str) -> dict[str, Any]:
    item = next((x for x in load_snapshot().get("events", []) if x.get("id") == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="News item not found")
    return item


def add_collection_routes(path: str, key: str) -> None:
    async def collection(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=settings.max_page_size),
        q: str | None = None,
        region: str | None = None,
        sector: str | None = None,
    ) -> dict[str, Any]:
        return filtered_page(key, page, page_size, q, region, sector)

    async def detail(slug: str) -> dict[str, Any]:
        item = find_by_slug(load_snapshot().get(key, []), slug)
        if item is None:
            raise HTTPException(status_code=404, detail=f"{key} item not found")
        return item

    app.add_api_route(f"/api/v1/{path}", collection, methods=["GET"], name=f"list_{key}")
    app.add_api_route(
        f"/api/v1/{path}/{{slug}}", detail, methods=["GET"], name=f"get_{key}"
    )


for route_path, snapshot_key in [
    ("sectors", "sectors"),
    ("companies", "companies"),
    ("institutions", "institutions"),
    ("ipo", "ipo"),
    ("people", "people"),
    ("reports", "reports"),
]:
    add_collection_routes(route_path, snapshot_key)


@app.get("/api/v1/search")
async def search(
    q: str = Query(min_length=1, max_length=120),
    item_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
) -> dict[str, Any]:
    snapshot = load_snapshot()
    mapping = {
        "company": "companies",
        "institution": "institutions",
        "sector": "sectors",
        "person": "people",
        "report": "reports",
        "event": "events",
    }
    keys = [mapping[item_type]] if item_type in mapping else list(mapping.values())
    matches: list[dict[str, Any]] = []
    for key in keys:
        for item in snapshot.get(key, []):
            if q.casefold() in str(item).casefold():
                matches.append({"type": key, **item})
    return paginated(matches, page, page_size)


@app.get("/api/v1/sources/{source_id}")
async def source(source_id: str) -> dict[str, Any]:
    sources = load_snapshot().get("sources", [])
    item = next((x for x in sources if x.get("id") == source_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return item


@app.post(
    "/api/internal/sync/run",
    dependencies=[Depends(verify_internal_secret)],
    response_model=SyncResult,
    include_in_schema=False,
)
async def internal_sync(request: SyncRequest) -> SyncResult:
    return await run_sync(source=request.source, force=request.force)


@app.post(
    "/api/internal/rebuild-snapshot",
    dependencies=[Depends(verify_internal_secret)],
    include_in_schema=False,
)
async def rebuild_snapshot() -> dict[str, str]:
    load_snapshot.cache_clear()
    return {"status": "reloaded"}


@app.post(
    "/api/internal/recalculate-heat",
    dependencies=[Depends(verify_internal_secret)],
    include_in_schema=False,
)
async def recalculate_heat() -> dict[str, str]:
    return {"status": "queued", "formula_version": "heat-v1"}
