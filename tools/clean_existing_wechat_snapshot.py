#!/usr/bin/env python3
"""Clean existing WeChat records without recrawling external sources."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:  # Imported by tests as tools.clean_existing_wechat_snapshot.
    from . import crawl_with_tracking as tracking
    from . import wechat_snapshot_quality as quality
except ImportError:  # Executed directly with python tools/...
    import crawl_with_tracking as tracking
    import wechat_snapshot_quality as quality

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"


def is_wechat_article(article: dict[str, Any]) -> bool:
    source = article.get("source", {})
    return bool(
        str(article.get("sourceId", "")).startswith("user-track-wechat-")
        or str(source.get("platform", "")).startswith("微信")
        or article.get("wechatAccount")
    )


def clean_snapshot(payload: dict[str, Any], tracking_payload: dict[str, Any]) -> dict[str, Any]:
    articles = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    wechat_articles = [item for item in articles if is_wechat_article(item)]
    non_wechat_count = len(articles) - len(wechat_articles)
    before_people = sum(len(item.get("mentionedPeople", [])) for item in wechat_articles)

    resolved = quality.resolve_cross_sector_articles(wechat_articles, tracking_payload)
    selected_by_url = {
        quality.canonical_url(item.get("source", {}).get("url", "")): item
        for item in resolved
        if quality.canonical_url(item.get("source", {}).get("url", ""))
    }
    selected_missing = [
        item
        for item in resolved
        if not quality.canonical_url(item.get("source", {}).get("url", ""))
    ]
    missing_index = 0
    emitted: set[str] = set()
    cleaned_articles: list[dict[str, Any]] = []

    for article in articles:
        if not is_wechat_article(article):
            cleaned_articles.append(article)
            continue
        key = quality.canonical_url(article.get("source", {}).get("url", ""))
        if key:
            if key in emitted:
                continue
            selected = selected_by_url.get(key)
            if selected:
                cleaned_articles.append(selected)
                emitted.add(key)
            continue
        if missing_index < len(selected_missing):
            cleaned_articles.append(selected_missing[missing_index])
            missing_index += 1

    cleaned_wechat = [item for item in cleaned_articles if is_wechat_article(item)]
    after_people = sum(len(item.get("mentionedPeople", [])) for item in cleaned_wechat)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    next_payload = dict(payload)
    next_payload["generatedAt"] = generated_at
    next_payload["articleCount"] = len(cleaned_articles)
    next_payload["articles"] = cleaned_articles

    ingestion = dict(payload.get("wechatIngestion", {}))
    ingestion.update(
        {
            "generatedAt": generated_at,
            "acceptedArticles": len(cleaned_wechat),
            "fullTextArticles": sum(
                1
                for item in cleaned_wechat
                if item.get("wechatContentMode") != "index-only"
            ),
            "indexOnlyArticles": sum(
                1
                for item in cleaned_wechat
                if item.get("wechatContentMode") == "index-only"
            ),
            "mentionedCompanyLinks": sum(
                len(item.get("mentionedCompanies", [])) for item in cleaned_wechat
            ),
            "mentionedPeopleLinks": after_people,
            "qualityCleanedAt": generated_at,
            "qualityRemovedCrossSectorDuplicates": max(
                0, len(wechat_articles) - len(cleaned_wechat)
            ),
            "qualityRemovedNonPeople": max(0, before_people - after_people),
            "nonWechatArticlesPreserved": non_wechat_count,
        }
    )
    next_payload["wechatIngestion"] = ingestion
    return next_payload


def comparable(payload: dict[str, Any]) -> dict[str, Any]:
    result = dict(payload)
    result.pop("generatedAt", None)
    ingestion = result.get("wechatIngestion")
    if isinstance(ingestion, dict):
        ingestion = dict(ingestion)
        ingestion.pop("generatedAt", None)
        ingestion.pop("qualityCleanedAt", None)
        result["wechatIngestion"] = ingestion
    return result


def main() -> int:
    payload = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
    next_payload = clean_snapshot(payload, tracking.load_tracking())
    if comparable(payload) == comparable(next_payload):
        print("No existing WeChat snapshot cleanup changes.")
        return 0
    OUTPUT_PATH.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(next_payload.get("wechatIngestion", {}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
