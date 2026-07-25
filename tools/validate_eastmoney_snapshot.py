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
INTERNAL_ARTICLE_FIELDS = {"_eastmoneyBatchOrigin"}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _host(url: str) -> str:
    host = (urlsplit(_clean(url)).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def _as_nonnegative_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


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


def _is_eastmoney_status(status: dict[str, Any]) -> bool:
    text = " ".join(
        _clean(status.get(key)) for key in ("id", "name", "company")
    )
    return "东方财富" in text or _host(_clean(status.get("url"))).endswith(
        "eastmoney.com"
    )


def _is_eastmoney_detail_status(status: dict[str, Any]) -> bool:
    status_id = _clean(status.get("id"))
    return (
        status_id.startswith("official-user-")
        or "newAccepted" in status
        or "retainedPreviousCount" in status
        or bool(status.get("retainedPrevious"))
    )


def _status_accounting_error(status: dict[str, Any]) -> str:
    has_accounting = (
        "newAccepted" in status
        or "retainedPreviousCount" in status
        or bool(status.get("retainedPrevious"))
    )
    if not has_accounting:
        return ""

    accepted = _as_nonnegative_int(status.get("accepted"))
    new_accepted = _as_nonnegative_int(status.get("newAccepted"))
    retained = _as_nonnegative_int(status.get("retainedPreviousCount"))
    status_id = _clean(status.get("id")) or "东方财富"

    if accepted != new_accepted + retained:
        return (
            f"{status_id}: accepted={accepted}, newAccepted={new_accepted}, "
            f"retainedPreviousCount={retained}"
        )
    if retained > 0 and not status.get("retainedPrevious"):
        return f"{status_id}: retainedPreviousCount>0 但未标记 retainedPrevious"
    if status.get("retainedPrevious") and retained == 0:
        return f"{status_id}: retainedPrevious=true 但保留数量为 0"
    return ""


def validate_snapshot(
    snapshot: dict[str, Any],
    tracking: dict[str, Any],
    *,
    require_attempt: bool = False,
) -> dict[str, Any]:
    enabled = _eastmoney_source_enabled(tracking)
    all_articles = [
        dict(raw)
        for raw in snapshot.get("articles", [])
        if isinstance(raw, dict)
    ]
    articles = [article for article in all_articles if _is_eastmoney_record(article)]
    attempt_statuses = [
        dict(raw)
        for raw in snapshot.get("sourceStatus", [])
        if isinstance(raw, dict) and _is_eastmoney_status(raw)
    ]
    detail_statuses = [
        status for status in attempt_statuses if _is_eastmoney_detail_status(status)
    ]

    detail_articles: list[dict[str, Any]] = []
    bad_urls: list[str] = []
    generic_duplicates: list[str] = []
    media_as_company: list[str] = []
    attributed_companies: set[str] = set()
    leaked_internal_fields: list[str] = []

    for article in all_articles:
        leaked = sorted(INTERNAL_ARTICLE_FIELDS & set(article))
        if leaked:
            label = _clean(article.get("title")) or _clean(article.get("id"))
            leaked_internal_fields.append(f"{label}: {', '.join(leaked)}")

    for article in articles:
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        source_url = _clean(source.get("url"))
        source_id = _clean(article.get("sourceId"))
        company = _clean(article.get("company"))
        is_detail = is_eastmoney_article_url(source_url)
        if source_id.startswith("user-source-") and not is_detail:
            generic_duplicates.append(source_url or source_id)
        if not is_detail:
            bad_urls.append(source_url or source_id)
            continue
        detail_articles.append(article)
        if company == "东方财富":
            media_as_company.append(_clean(article.get("title")) or source_url)
        elif company and company not in {"科技产业", "未识别", "unknown"}:
            attributed_companies.add(company)

    accepted = sum(
        _as_nonnegative_int(status.get("accepted")) for status in detail_statuses
    )
    accounting_errors = [
        error
        for status in detail_statuses
        if (error := _status_accounting_error(status))
    ]
    attempted = bool(attempt_statuses)
    errors: list[str] = []

    if leaked_internal_fields:
        errors.append(
            f"公开快照泄露 {len(leaked_internal_fields)} 条东方财富流水线内部字段"
        )
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
    if accounting_errors:
        errors.append(f"东方财富滚动历史计数不闭合：{len(accounting_errors)} 个来源")
    if require_attempt and enabled and not attempted:
        errors.append("东方财富来源已启用，但快照中没有对应抓取状态")
    if detail_articles and not detail_statuses:
        errors.append("快照中存在东方财富详情文章，但缺少专用详情抓取状态")
    if accepted > 0 and not detail_articles:
        errors.append("抓取状态显示已接受文章，但快照中没有东方财富详情页")
    if detail_statuses and accepted != len(detail_articles):
        errors.append(
            "东方财富来源 accepted 与最终详情文章数不一致："
            f"accepted={accepted}, detailArticles={len(detail_articles)}"
        )

    report = {
        "enabled": enabled,
        "attempted": attempted,
        "attemptStatusCount": len(attempt_statuses),
        "detailStatusCount": len(detail_statuses),
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
        "leakedInternalFields": leaked_internal_fields[:8],
        "accountingErrors": accounting_errors[:8],
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
