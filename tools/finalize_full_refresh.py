#!/usr/bin/env python3
"""Finalize a completed full-source intelligence refresh.

All source statuses in the snapshot are known to belong to this run because
``prepare_full_refresh.py`` clears the ledger before network crawling starts.
This script stamps those rows with one completion timestamp and publishes a
compact audit summary for the UI and validators.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
TAIPEI = ZoneInfo("Asia/Taipei")
PIPELINE_STAGES = [
    "core-and-tracking-sources",
    "official-company-sources",
    "market-profiles",
    "entity-migration",
    "eastmoney-refinement",
    "tracking-enrichment",
    "people-profiles",
]


def _source_key(article: dict) -> str:
    source_id = str(article.get("sourceId") or "").strip()
    if source_id:
        return source_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("name") or "unknown").strip() or "unknown"


def main() -> int:
    if not ARTICLES_PATH.exists():
        raise SystemExit(f"missing snapshot: {ARTICLES_PATH}")

    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")

    completed_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    local_date = datetime.now(TAIPEI).date().isoformat()
    articles = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    statuses = [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)]

    for status in statuses:
        status["lastAttemptAt"] = completed_at

    status_counts = Counter(str(item.get("status") or "unknown") for item in statuses)
    today_articles = [item for item in articles if item.get("publishedAt") == local_date]
    today_sources = Counter(_source_key(item) for item in today_articles)
    latest_published_at = max(
        (str(item.get("publishedAt") or "") for item in articles),
        default="",
    )

    payload["sourceStatus"] = statuses
    payload["refreshAudit"] = {
        "mode": "full",
        "pipelineCompleted": True,
        "completedAt": completed_at,
        "localDate": local_date,
        "stages": PIPELINE_STAGES,
        "articleCount": len(articles),
        "latestPublishedAt": latest_published_at,
        "todayArticleCount": len(today_articles),
        "todaySourceCount": len(today_sources),
        "todaySources": dict(sorted(today_sources.items())),
        "sourceStatusCount": len(statuses),
        "sourceStatusCounts": dict(sorted(status_counts.items())),
        "healthySourceCount": sum(
            item.get("status") in {"ok", "partial"}
            and int(item.get("accepted", 0) or 0) > 0
            for item in statuses
        ),
        "failedSourceCount": status_counts.get("error", 0),
        "retainedPreviousSourceCount": sum(
            bool(item.get("retainedPrevious")) for item in statuses
        ),
    }

    ARTICLES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["refreshAudit"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
