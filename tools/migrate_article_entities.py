#!/usr/bin/env python3
"""Clean legacy entity attribution created before source categories existed.

The migration is intentionally narrow: it only touches articles that can be
matched to a configured non-company user source by source id, source name or
source host. Real company attribution inferred from article content is kept.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
VALID_CATEGORIES = {"company", "media", "person"}
GENERIC_COMPANY = "科技产业"


def clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def slug(value: Any) -> str:
    text = clean(value, 100).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:80] or "source"


def normalized_host(url: Any) -> str:
    host = (urlsplit(clean(url)).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def source_category(raw: dict[str, Any]) -> str:
    explicit = clean(raw.get("sourceCategory"), 20)
    if explicit in VALID_CATEGORIES:
        return explicit
    if (
        clean(raw.get("sourceType"), 30) == "sec"
        or clean(raw.get("ticker"), 30)
        or clean(raw.get("listedCompanyId"), 100)
    ):
        return "company"
    return "media"


def is_non_article(title: str, url: str) -> bool:
    folded = title.casefold()
    path = urlsplit(url).path.casefold().rstrip("/")
    title_markers = (
        "的文章_",
        "的文章 -",
        "的文章 |",
        "articles by ",
        "author profile",
        "作者主页",
        "个人主页",
        "全部文章",
        "文章列表",
    )
    if any(marker in folded for marker in title_markers):
        return True
    profile_patterns = (
        r"/(?:author|authors|profile|profiles|columnist|contributors?)/[^/]+$",
        r"/(?:media|user|users|member|members)/(?:m|u|user)?\d+$",
        r"/(?:tag|tags|category|categories|channel|channels)/[^/]+$",
    )
    return any(re.search(pattern, path) for pattern in profile_patterns)


def build_non_company_index(tracking: dict[str, Any]) -> dict[str, dict[str, str]]:
    by_id: dict[str, str] = {}
    by_name: dict[str, str] = {}
    by_host: dict[str, str] = {}
    aliases: set[str] = set()

    for index, raw in enumerate(tracking.get("sources", [])):
        if not isinstance(raw, dict):
            continue
        category = source_category(raw)
        if category == "company":
            continue
        name = clean(raw.get("name"), 100)
        raw_id = clean(raw.get("id"), 120)
        company = clean(raw.get("company"), 100)
        host = normalized_host(raw.get("url"))
        source_key = raw_id or name or str(index)
        ids = {
            raw_id,
            f"user-source-{slug(source_key)}",
            f"official-user-{slug(company or name)}",
        }
        for source_id in ids:
            if source_id:
                by_id[source_id] = category
        if name:
            by_name[name.casefold()] = category
            aliases.add(name.casefold())
        if company:
            aliases.add(company.casefold())
        if host:
            by_host[host] = category

    return {
        "by_id": by_id,
        "by_name": by_name,
        "by_host": by_host,
        "aliases": {value: "1" for value in aliases},
    }


def article_category(article: dict[str, Any], index: dict[str, dict[str, str]]) -> str:
    source_id = clean(article.get("sourceId"), 160)
    if source_id in index["by_id"]:
        return index["by_id"][source_id]
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_name = clean(source.get("name"), 100).casefold()
    if source_name in index["by_name"]:
        return index["by_name"][source_name]
    host = normalized_host(source.get("url"))
    return index["by_host"].get(host, "")


def migrate(payload: dict[str, Any], tracking: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    index = build_non_company_index(tracking)
    report = {
        "removedNonArticles": 0,
        "clearedFakeCompanies": 0,
        "removedFakeCompanySlugs": 0,
        "relabelledSources": 0,
        "removedLegacyStatuses": 0,
    }
    migrated: list[dict[str, Any]] = []

    for raw in payload.get("articles", []):
        if not isinstance(raw, dict):
            continue
        article = dict(raw)
        category = article_category(article, index)
        if category not in {"media", "person"}:
            migrated.append(article)
            continue

        source = dict(article.get("source")) if isinstance(article.get("source"), dict) else {}
        source_url = clean(source.get("url"), 500)
        if is_non_article(clean(article.get("title"), 300), source_url):
            report["removedNonArticles"] += 1
            continue

        company = clean(article.get("company"), 100)
        source_name = clean(source.get("name"), 100)
        fake_company = (
            company.casefold() in index["aliases"]
            or (source_name and company.casefold() == source_name.casefold())
        )
        company_slug = clean(article.get("companySlug"), 100)
        fake_slug = company_slug.startswith("user-") or (
            fake_company and company_slug == slug(company)
        )

        if fake_company:
            article["company"] = GENERIC_COMPANY
            report["clearedFakeCompanies"] += 1
        if fake_slug:
            article.pop("companySlug", None)
            report["removedFakeCompanySlugs"] += 1

        expected_level = "人物公开信息" if category == "person" else "媒体报道"
        if source.get("level") == "官方披露" or clean(article.get("sourceId")).startswith("official-user-"):
            source["level"] = expected_level
            article["source"] = source
            report["relabelledSources"] += 1

        migrated.append(article)

    statuses: list[dict[str, Any]] = []
    for status in payload.get("sourceStatus", []):
        if not isinstance(status, dict):
            continue
        status_id = clean(status.get("id"), 160)
        if status_id.startswith("official-user-") and status_id in index["by_id"]:
            report["removedLegacyStatuses"] += 1
            continue
        statuses.append(status)

    result = dict(payload)
    result["articles"] = migrated
    result["articleCount"] = len(migrated)
    if isinstance(payload.get("sourceStatus"), list):
        result["sourceStatus"] = statuses
    if any(report.values()):
        result["generatedAt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return result, report


def main() -> int:
    if not TRACKING_PATH.exists() or not ARTICLES_PATH.exists():
        raise SystemExit("tracking configuration or article snapshot is missing")
    tracking = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    migrated, report = migrate(payload, tracking)
    if migrated != payload:
        ARTICLES_PATH.write_text(
            json.dumps(migrated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
