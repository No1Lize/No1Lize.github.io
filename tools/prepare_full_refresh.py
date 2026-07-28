#!/usr/bin/env python3
"""Prepare an atomic full-source intelligence refresh.

The snapshot historically merged new source statuses into old ones. That made a
partial crawler run look like a complete run because stale success rows remained
visible. A full refresh must start with an empty status ledger; every configured
crawler then writes a fresh status row, including explicit errors and empty
results. The repository file is only committed after the whole workflow passes.

A temporary article-id baseline is embedded in the working snapshot so the
finalizer can report how many records were newly added by this refresh. The
baseline is removed before publication.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
REFRESH_BASELINE_KEY = "_refreshBaseline"


def _article_identity(article: dict) -> str:
    article_id = str(article.get("id") or "").strip()
    if article_id:
        return article_id
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return str(source.get("url") or "").strip()


def main() -> int:
    if not ARTICLES_PATH.exists():
        raise SystemExit(f"missing snapshot: {ARTICLES_PATH}")

    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("article snapshot must be a JSON object")

    previous_statuses = payload.get("sourceStatus", [])
    previous_count = len(previous_statuses) if isinstance(previous_statuses, list) else 0
    previous_articles = [
        item for item in payload.get("articles", []) if isinstance(item, dict)
    ]
    baseline_ids = sorted(
        identity
        for identity in (_article_identity(item) for item in previous_articles)
        if identity
    )

    payload[REFRESH_BASELINE_KEY] = {
        "articleCount": len(previous_articles),
        "articleIds": baseline_ids,
    }
    payload["sourceStatus"] = []
    payload["qualityGate"] = {}
    payload.pop("refreshAudit", None)
    payload.pop("trackingConfigHash", None)
    payload.pop("trackingEnrichedAt", None)
    payload.pop("trackCoverage", None)

    ARTICLES_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "clearedSourceStatuses": previous_count,
                "baselineArticleCount": len(previous_articles),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
