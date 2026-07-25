#!/usr/bin/env python3
"""Run the public crawler with category-aware user source routing.

This module deliberately wraps ``crawl_with_tracking`` rather than duplicating
its crawler, quality-gate and person-label logic. It replaces only the custom
source conversion step so media and person sources never inherit a fabricated
company entity.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit

try:  # Imported by tests as tools.crawl_with_source_categories.
    from . import crawl_with_tracking as tracking
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_with_tracking as tracking


VALID_SOURCE_CATEGORIES = {"company", "media", "person"}
EVENT_TERMS = (
    "融资 OR 投资 OR IPO OR 上市 OR 公告 OR 财报 OR 发布 OR 突破 "
    "OR funding OR investment OR filing OR earnings OR launch OR research"
)
PERSON_EVENT_TERMS = (
    "访谈 OR 观点 OR 演讲 OR 研究 OR 发布 OR interview OR opinion OR talk OR research OR post"
)


def source_category(raw: dict[str, Any], source_type: str | None = None) -> str:
    """Return an explicit category or safely migrate a legacy source row."""

    explicit = tracking._clean(raw.get("sourceCategory"), 20)
    if explicit in VALID_SOURCE_CATEGORIES:
        return explicit
    normalized_type = source_type or tracking._clean(raw.get("sourceType"), 30)
    if (
        normalized_type == "sec"
        or tracking._clean(raw.get("ticker"), 30)
        or tracking._clean(raw.get("listedCompanyId"), 100)
    ):
        return "company"
    return "media"


def _listed_company_index(tracking_config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in tracking_config.get("listedCompanies", []):
        if not isinstance(raw, dict):
            continue
        company_id = tracking._clean(raw.get("id"), 100)
        if company_id:
            result[company_id] = raw
    return result


def _category_keywords(
    raw: dict[str, Any],
    category: str,
    track_by_name: dict[str, dict[str, Any]],
) -> list[str]:
    sanitized = dict(raw)
    if category != "company":
        sanitized["company"] = ""
        sanitized["ticker"] = ""
    return tracking._source_keywords(sanitized, track_by_name)


def _custom_sources(
    tracking_config: dict[str, Any], tracks: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, str, str]]]:
    feed_specs: list[dict[str, Any]] = []
    sec_specs: dict[str, tuple[str, str, str, str]] = {}
    track_by_name = {track["name"].casefold(): track for track in tracks}
    listed_by_id = _listed_company_index(tracking_config)

    for index, raw in enumerate(tracking_config.get("sources", [])):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue

        name = tracking._clean(raw.get("name"), 80)
        source_type = tracking._clean(raw.get("sourceType"), 30) or "listing-search"
        category = source_category(raw, source_type)
        company = tracking._clean(raw.get("company"), 80)
        ticker = tracking._clean(raw.get("ticker"), 30).upper()
        region = tracking._clean(raw.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = tracking._clean(raw.get("sector"), 60) or "AI / AGI"
        url = tracking._clean(raw.get("url"), 500)
        source_id = f"user-source-{tracking._slug(raw.get('id') or name or index)}"
        if not name:
            continue

        linked_company = listed_by_id.get(
            tracking._clean(raw.get("listedCompanyId"), 100), {}
        )
        if category == "company":
            company = company or tracking._clean(linked_company.get("name"), 80) or name
            ticker = ticker or tracking._clean(linked_company.get("ticker"), 30).upper()

        if source_type == "sec":
            if category == "company" and ticker:
                company_slug = (
                    tracking._clean(linked_company.get("catalogSlug"), 80)
                    or tracking._slug(company)
                )
                sec_specs[ticker] = (company, company_slug, sector, region)
            continue

        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue

        keywords = _category_keywords(raw, category, track_by_name)
        allowed_hosts: list[str] = []
        if source_type == "rss":
            feed_url = url
            platform = {
                "company": "用户公司 RSS",
                "media": "用户媒体 RSS",
                "person": "用户人物 RSS",
            }[category]
        else:
            host = (urlsplit(url).hostname or "").lower().removeprefix("www.")
            if not host:
                continue
            allowed_hosts = [host]
            if category == "company":
                identity_terms = tracking._unique([company, ticker, *keywords], 16)
                query = f"site:{host} ({tracking._quoted_or_query(identity_terms)}) ({EVENT_TERMS})"
                platform = "用户公司来源"
            elif category == "person":
                identity_terms = tracking._unique([name, *keywords], 16)
                query = (
                    f"site:{host} ({tracking._quoted_or_query(identity_terms)}) "
                    f"({PERSON_EVENT_TERMS})"
                )
                platform = "用户人物来源"
            else:
                topic_terms = tracking._unique(keywords, 16)
                query = f"site:{host} ({tracking._quoted_or_query(topic_terms)}) ({EVENT_TERMS})"
                platform = "用户媒体来源"
            feed_url = tracking._bing_rss(query)

        spec: dict[str, Any] = {
            "id": source_id,
            "name": name,
            "url": feed_url,
            "adapter": "rss",
            "platform": platform,
            "sourceCategory": category,
            "sourceLevel": "待交叉验证",
            "region": region,
            "sector": sector,
            "maxItems": 10,
            "keywords": keywords,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        if category == "company":
            company_slug = (
                tracking._clean(linked_company.get("catalogSlug"), 80)
                or tracking._slug(company)
            )
            spec["company"] = company
            spec["companySlug"] = company_slug
        if allowed_hosts:
            spec["allowedHosts"] = allowed_hosts
        feed_specs.append(spec)

    return feed_specs[:60], sec_specs


def main() -> int:
    tracking._custom_sources = _custom_sources
    return tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
