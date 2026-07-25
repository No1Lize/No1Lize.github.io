#!/usr/bin/env python3
"""Validate Eastmoney records in the generated public intelligence snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

try:
    from .eastmoney_entities import is_eastmoney_article_url
except ImportError:
    from eastmoney_entities import is_eastmoney_article_url


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = ROOT / "public" / "data" / "articles.json"
TRACKING_PATH = ROOT / "config" / "user_tracking.json"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _host(url: str) -> str:
    host = (urlsplit(_clean(url)).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _eastmoney_source_enabled(tracking: dict[str, Any]) -> bool:
    for raw in tracking.get("sources", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = _clean(raw.get("name"))
        company = _clean(raw.get("company"))
        url = _clean(raw.get("url"))
        if "东方财富" in f"{name} {company}" or _host(url).endswith(
            "eastmoney.com"
        ):
            return True
    return False


def _is_eastmoney_record(article: dict[str, Any]) -> bool:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_id = _clean(article.get("sourceId"))
    source_name = _clean(source.get("name"))
    source_url = _clean(source.get("url"))
    return (
        "东方财富" in f"{source_id} {source_name}"
        or _host(source_url).endswith("eastmoney.com")
    )


def validate_snapshot(
    snapshot: dict[str, Any],
    tracking: dict[str, Any],
    *,
    require_attempt: bool = False,
) -> dict[str, Any]:
    enabled = _eastmoney_source_enabled(tracking)
    articles = [
        dict(raw)
        for raw in snapshot.get("articles", [])
        if isinstance(raw, dict) and _is_eastmoney_record(raw)
    ]
    statuses = [
        dict(raw)
        for raw in snapshot.get("sourceStatus", [])
        if isinstance(raw, dict)
        and (
            "东方财富"
            in f"{_clean(raw.get('id'))} {_clean(raw.get('name'))} {_clean(raw.get('company'))}"
            or _host(_clean(raw.get("url"))).endswith("eastmoney.com")
        )
    ]

    detail_articles: list[dict[str, Any]] = []
    bad_urls: list[str] = []
    generic_duplicates: list[str] = []
    media_as_company: list[str] = []
    attributed_companies: set[str] = set()

    for article in articles:
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        source_url = _clean(source.get("url"))
        source_id = _clean(article.get("sourceId"))
        company = _clean(article.get("company"))
        if source_id.startswith("user-source-"):
            generic_duplicates.append(source_url or source_id)
        if not is_eastmoney_article_url(source_url):
            bad_urls.append(source_url or source_id)
            continue
        detail_articles.append(article)
        if company == "东方财富":
            media_as_company.append(_clean(article.get("title")) or source_url)
        elif company and company not in {"科技产业", "未识别", "unknown"}:
            attributed_companies.add(company)

    accepted = sum(int(status.get("accepted", 0) or 0) for status in statuses)
    attempted = bool(statuses)
    errors: list[str] = []
    if generic_duplicates:
        errors.append(
            f"仍有 {len(generic_duplicates)} 条东方财富泛化 user-source 重复记录"
        )
    if bad_urls:
        errors.append(f"仍有 {len(bad_urls)} 条东方财富首页或栏目页记录")
    if media_as_company:
        errors.append(
            f"仍有 {len(media_as_company)} 条详情文章把媒体错误写成被报道公司"
        )
    if require_attempt and enabled and not attempted:
        errors.append("东方财富来源已启用，但快照中没有对应抓取状态")
    if accepted > 0 and not detail_articles:
        errors.append("抓取状态显示已接受文章，但快照中没有东方财富详情页")

    report = {
        "enabled": enabled,
        "attempted": attempted,
        "acceptedByCrawler": accepted,
        "eastmoneyRecords": len(articles),
        "detailArticles": len(detail_articles),
        "attributedArticles": sum(
            1
            for article in detail_articles
            if _clean(article.get("company"))
            not in {"", "科技产业", "东方财富", "未识别", "unknown"}
        ),
        "companies": sorted(attributed_companies),
        "badUrls": bad_urls[:8],
        "genericDuplicates": generic_duplicates[:8],
        "mediaAsCompany": media_as_company[:8],
        "errors": errors,
    }
    if errors:
        raise ValueError(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--tracking", type=Path, default=TRACKING_PATH)
    parser.add_argument("--require-attempt", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    tracking = json.loads(args.tracking.read_text(encoding="utf-8"))
    report = validate_snapshot(
        snapshot,
        tracking,
        require_attempt=args.require_attempt,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
