from datetime import UTC, datetime

import httpx
import structlog

from backend.app.schemas import SyncResult
from .dedupe import deduplicate
from .sources.openai_news import OpenAINewsAdapter
from .sources.sec_submissions import SecSubmissionsAdapter

logger = structlog.get_logger()
ADAPTERS = {"openai": OpenAINewsAdapter(), "sec": SecSubmissionsAdapter()}


async def run_sync(source: str | None = None, force: bool = False) -> SyncResult:
    started_at = datetime.now(UTC)
    selected = [ADAPTERS[source]] if source in ADAPTERS else list(ADAPTERS.values())
    candidates = []
    errors = 0
    async with httpx.AsyncClient() as client:
        for adapter in selected:
            try:
                candidates.extend(await adapter.collect(client))
            except Exception as exc:
                errors += 1
                logger.warning(
                    "source_sync_failed",
                    source=adapter.name,
                    error_type=type(exc).__name__,
                    force=force,
                )
    unique, skipped = deduplicate(candidates)
    # Database upserts are intentionally isolated from collection. The initial release
    # exposes the checked-in snapshot until DATABASE_URL is configured and migrated.
    return SyncResult(
        status="partial" if errors else "ok",
        started_at=started_at,
        scanned=len(candidates),
        created=len(unique),
        updated=0,
        skipped=skipped,
        conflicts=0,
        errors=errors,
    )
