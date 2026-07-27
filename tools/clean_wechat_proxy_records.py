#!/usr/bin/env python3
"""Remove aggregation/index pages that were incorrectly published as WeChat articles."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from . import refresh_wechat_snapshot as refresh
except ImportError:
    import refresh_wechat_snapshot as refresh

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def clean_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    articles = [
        article for article in payload.get("articles", []) if isinstance(article, dict)
    ]
    retained = [article for article in articles if refresh._publishable_article(article)]
    removed = len(articles) - len(retained)
    if not removed:
        return payload, 0

    next_payload = dict(payload)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    next_payload["generatedAt"] = generated_at
    next_payload["articleCount"] = len(retained)
    next_payload["articles"] = retained

    direct_by_source: dict[str, int] = {}
    for article in retained:
        if not refresh._is_wechat_record(article):
            continue
        source_id = str(article.get("sourceId", ""))
        direct_by_source[source_id] = direct_by_source.get(source_id, 0) + 1

    statuses: list[dict[str, Any]] = []
    for raw in payload.get("sourceStatus", []):
        if not isinstance(raw, dict):
            continue
        status = dict(raw)
        source_id = str(status.get("id", ""))
        if source_id.startswith("user-track-wechat-"):
            accepted = direct_by_source.get(source_id, 0)
            status["accepted"] = accepted
            status.pop("indexOnly", None)
            if accepted == 0 and status.get("status") in {"ok", "partial"}:
                status["status"] = "error"
                status["failed"] = max(1, int(status.get("failed", 0) or 0))
                status["error"] = "Proxy/index records removed; awaiting original WeChat page"
        statuses.append(status)
    next_payload["sourceStatus"] = statuses

    ingestion = dict(payload.get("wechatIngestion", {}))
    ingestion.update(
        {
            "generatedAt": generated_at,
            "acceptedArticles": sum(direct_by_source.values()),
            "fullTextArticles": sum(direct_by_source.values()),
            "indexOnlyArticles": 0,
            "removedProxyRecords": int(ingestion.get("removedProxyRecords", 0) or 0)
            + removed,
        }
    )
    next_payload["wechatIngestion"] = ingestion
    return next_payload, removed


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    next_payload, removed = clean_payload(payload)
    if not removed:
        print("No WeChat proxy records found.")
        return 0
    ARTICLES_PATH.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Removed {removed} WeChat proxy/index records.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
