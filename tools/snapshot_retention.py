#!/usr/bin/env python3
"""Apply and validate rolling retention for the formal article snapshot.

When the snapshot reaches its capacity, articles are ordered newest-first by
``publishedAt``. Newer records remain in the snapshot and the oldest records
fall off the tail. Importance and article id provide deterministic tie-breaks
for records published on the same date.

The retention pass also removes duplicate source URLs. This is intentionally
run again after a workflow rebase so a concurrent data commit cannot introduce
one duplicate URL and block publication of an otherwise valid refresh.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    from . import crawl_articles as crawler
except ImportError:
    import crawl_articles as crawler

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
RETENTION_SCHEMA_VERSION = 2
RETENTION_STRATEGY = "newest-published-first"
OVERFLOW_ACTION = "discard-oldest"
TRACKING_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "share_from",
    "share_source",
    "share_token",
    "spm",
}


def _published_ordinal(article: dict[str, Any]) -> int:
    value = str(article.get("publishedAt", "")).strip()
    try:
        return date.fromisoformat(value).toordinal()
    except ValueError:
        return 0


def article_sort_key(article: dict[str, Any]) -> tuple[int, int, str]:
    return (
        _published_ordinal(article),
        int(article.get("importance", 0) or 0),
        str(article.get("id", "")),
    )


def canonical_article_url(article: dict[str, Any]) -> str:
    """Return a stable URL key without fragments or known tracking parameters."""

    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    raw_url = str(source.get("url") or "").strip()
    if not raw_url:
        return f"id:{str(article.get('id') or '').strip()}"

    try:
        parts = urlsplit(raw_url)
    except ValueError:
        return raw_url.rstrip("/")

    if not parts.scheme or not parts.netloc:
        return raw_url.rstrip("/")

    filtered_query = sorted(
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and key.lower() not in TRACKING_QUERY_KEYS
    )
    path = parts.path or "/"
    if path != "/":
        path = path.rstrip("/")

    return urlunsplit(
        (
            parts.scheme.lower(),
            parts.netloc.lower(),
            path,
            urlencode(filtered_query, doseq=True),
            "",
        )
    )


def retain_latest_articles(
    articles: Iterable[dict[str, Any]],
    capacity: int,
) -> list[dict[str, Any]]:
    if capacity <= 0:
        raise ValueError("snapshot capacity must be positive")

    rows = sorted(
        (article for article in articles if isinstance(article, dict)),
        key=article_sort_key,
        reverse=True,
    )
    retained: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for article in rows:
        canonical_url = canonical_article_url(article)
        if canonical_url in seen_urls:
            continue
        seen_urls.add(canonical_url)
        retained.append(article)
        if len(retained) >= capacity:
            break
    return retained


def retention_metadata(capacity: int) -> dict[str, Any]:
    return {
        "schemaVersion": RETENTION_SCHEMA_VERSION,
        "strategy": RETENTION_STRATEGY,
        "capacity": capacity,
        "overflowAction": OVERFLOW_ACTION,
        "deduplicateBy": "canonical-source-url",
        "sortFields": ["publishedAt:desc", "importance:desc", "id:desc"],
    }


def apply_retention(
    payload: dict[str, Any],
    capacity: int = crawler.MAX_ARTICLES,
) -> tuple[dict[str, Any], int]:
    raw_articles = [
        article for article in payload.get("articles", []) if isinstance(article, dict)
    ]
    retained = retain_latest_articles(raw_articles, capacity)
    removed = max(0, len(raw_articles) - len(retained))
    next_payload = dict(payload)
    next_payload["articleCount"] = len(retained)
    next_payload["articles"] = retained
    next_payload["snapshotRetention"] = retention_metadata(capacity)
    return next_payload, removed


def validate_retention(
    payload: dict[str, Any],
    capacity: int = crawler.MAX_ARTICLES,
) -> list[str]:
    errors: list[str] = []
    articles = [
        article for article in payload.get("articles", []) if isinstance(article, dict)
    ]
    expected = retain_latest_articles(articles, capacity)
    canonical_urls = [canonical_article_url(article) for article in articles]
    if len(articles) > capacity:
        errors.append(f"articleCount exceeds capacity: {len(articles)} > {capacity}")
    if len(canonical_urls) != len(set(canonical_urls)):
        errors.append("articles contain duplicate canonical source URLs")
    if articles != expected:
        errors.append("articles are not ordered by the rolling newest-first policy")
    if int(payload.get("articleCount", -1)) != len(articles):
        errors.append("articleCount does not match the retained article array")
    if payload.get("snapshotRetention") != retention_metadata(capacity):
        errors.append("snapshotRetention metadata is missing or stale")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--capacity", type=int, default=crawler.MAX_ARTICLES)
    args = parser.parse_args()

    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    if args.check:
        errors = validate_retention(payload, args.capacity)
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {
                    "passed": True,
                    "capacity": args.capacity,
                    "articleCount": len(payload.get("articles", [])),
                    "strategy": RETENTION_STRATEGY,
                },
                ensure_ascii=False,
            )
        )
        return 0

    next_payload, removed = apply_retention(payload, args.capacity)
    if next_payload == payload:
        print("Snapshot retention already satisfied.")
        return 0
    ARTICLES_PATH.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "capacity": args.capacity,
                "retained": len(next_payload.get("articles", [])),
                "removedOldestOrDuplicate": removed,
                "strategy": RETENTION_STRATEGY,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
