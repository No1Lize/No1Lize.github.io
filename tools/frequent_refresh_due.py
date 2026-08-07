#!/usr/bin/env python3
"""Decide whether the lightweight public-intelligence crawl is actually due."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
MIN_CRAWL_AGE_MINUTES = 90


def _parse_timestamp(value: Any) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def last_news_crawl_at(payload: dict[str, Any]) -> str:
    audit = payload.get("refreshAudit")
    if not isinstance(audit, dict):
        return ""
    explicit = str(audit.get("lastNewsCrawlAt") or "").strip()
    if explicit:
        return explicit

    # Backward-compatible fallback for snapshots produced before the
    # dedicated source-crawl clock existed. Only a completed full/frequent
    # pipeline can establish freshness; generic generatedAt is deliberately
    # ignored because derived-data jobs also change it.
    if audit.get("pipelineCompleted") is not True:
        return ""
    if str(audit.get("mode") or "") not in {"full", "frequent"}:
        return ""
    stages = audit.get("stages")
    if isinstance(stages, list) and stages and "core-and-tracking-sources" not in stages:
        return ""
    return str(audit.get("completedAt") or "").strip()


def evaluate_due(
    payload: dict[str, Any],
    *,
    event_name: str,
    now: datetime | None = None,
    min_age_minutes: int = MIN_CRAWL_AGE_MINUTES,
) -> dict[str, Any]:
    raw = last_news_crawl_at(payload)
    if event_name == "workflow_dispatch":
        return {
            "due": True,
            "ageMinutes": 0,
            "lastNewsCrawlAt": raw,
            "reason": "manual-dispatch",
        }

    last = _parse_timestamp(raw)
    if last is None:
        return {
            "due": True,
            "ageMinutes": -1,
            "lastNewsCrawlAt": raw,
            "reason": "missing-news-crawl-audit",
        }

    current = (now or datetime.now(UTC)).astimezone(UTC)
    age_minutes = max(0, int((current - last).total_seconds() // 60))
    return {
        "due": age_minutes >= min_age_minutes,
        "ageMinutes": age_minutes,
        "lastNewsCrawlAt": raw,
        "reason": "age-threshold",
    }


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be an object")
    result = evaluate_due(payload, event_name=os.environ.get("EVENT_NAME", ""))
    print(json.dumps(result, ensure_ascii=False))
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output:
            output.write(f"due={str(result['due']).lower()}\n")
            output.write(f"age_minutes={result['ageMinutes']}\n")
            output.write(f"last_news_crawl_at={result['lastNewsCrawlAt']}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
