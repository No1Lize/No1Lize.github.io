#!/usr/bin/env python3
"""Add bounded progress reporting around professional-media source batches."""

from __future__ import annotations

import sys
from typing import Any, Sequence

BATCH_SIZE = 10


def _is_professional_media(spec: dict[str, Any]) -> bool:
    return spec.get("adapter") == "professional_media"


def install(crawler: Any, batch_size: int = BATCH_SIZE) -> None:
    """Run professional media in visible batches without changing source logic."""

    original_group = crawler._crawl_config_group
    if getattr(original_group, "_professional_media_progress", False):
        return
    batch_size = max(1, int(batch_size))

    def crawl_group(
        specs: Sequence[dict[str, Any]],
        user_agent: str,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
        rows = list(specs)
        media_specs = [spec for spec in rows if _is_professional_media(spec)]
        other_specs = [spec for spec in rows if not _is_professional_media(spec)]

        articles, statuses, errors = original_group(other_specs, user_agent)
        if not media_specs:
            return articles, statuses, errors

        total = len(media_specs)
        accepted = 0
        successful = 0
        print(
            f"professional-media progress=0/{total} accepted=0 successful=0",
            file=sys.stderr,
            flush=True,
        )
        for offset in range(0, total, batch_size):
            chunk = media_specs[offset : offset + batch_size]
            batch_articles, batch_statuses, batch_errors = original_group(
                chunk,
                user_agent,
            )
            articles.extend(batch_articles)
            statuses.extend(batch_statuses)
            errors.extend(batch_errors)
            accepted += sum(int(row.get("accepted", 0) or 0) for row in batch_statuses)
            successful += sum(
                row.get("status") in {"ok", "partial"}
                and int(row.get("accepted", 0) or 0) > 0
                for row in batch_statuses
            )
            completed = min(offset + len(chunk), total)
            print(
                "professional-media "
                f"progress={completed}/{total} "
                f"accepted={accepted} successful={successful}",
                file=sys.stderr,
                flush=True,
            )

        return articles, sorted(statuses, key=lambda row: str(row.get("id", ""))), errors

    setattr(crawl_group, "_professional_media_progress", True)
    crawler._crawl_config_group = crawl_group
