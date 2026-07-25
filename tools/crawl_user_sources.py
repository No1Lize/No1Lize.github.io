#!/usr/bin/env python3
"""Unified entry point for all browser-managed public sources."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from . import crawl_with_tracking as tracking
    from . import generic_web_sources
    from .crawl_tracked_articles import configure_crawler, _install_empty_sec_guard
except ImportError:
    import crawl_with_tracking as tracking
    import generic_web_sources
    from crawl_tracked_articles import configure_crawler, _install_empty_sec_guard


def _source_level(category: str) -> str:
    return {
        "company": "官方披露",
        "person": "原始材料",
        "media": "媒体报道",
    }.get(category, "待交叉验证")


def _custom_sources(
    tracking_config: dict[str, Any],
    tracks: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, tuple[str, str, str, str]]]:
    """Convert every enabled source into a typed runtime adapter.

    RSS remains RSS; SEC remains SEC; every other public website uses the
    language-aware generic adapter. Eastmoney stays on its specialized direct
    crawler because that parser has stricter article and body extraction rules.
    """

    specs: list[dict[str, Any]] = []
    sec_specs: dict[str, tuple[str, str, str, str]] = {}
    track_by_name = {track["name"].casefold(): track for track in tracks}

    for index, raw in enumerate(tracking_config.get("sources", [])):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue

        raw_name = tracking._clean(raw.get("name"), 80)
        source_type = tracking._clean(raw.get("sourceType"), 30) or "listing-search"
        category = tracking._clean(raw.get("sourceCategory"), 20)
        if category not in {"company", "media", "person"}:
            category = "company" if raw.get("company") or raw.get("ticker") else "media"

        url = tracking._clean(raw.get("url"), 500)
        host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
        display_name = raw_name
        if not display_name or re.match(r"^https?://", display_name, re.IGNORECASE):
            display_name = host or f"用户来源 {index + 1}"

        company = (
            tracking._clean(raw.get("company"), 80)
            if category == "company"
            else ""
        )
        ticker = (
            tracking._clean(raw.get("ticker"), 30).upper()
            if category == "company"
            else ""
        )
        region = tracking._clean(raw.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = tracking._clean(raw.get("sector"), 60) or "AI / AGI"
        source_id = f"user-source-{tracking._slug(raw.get('id') or display_name or index)}"

        if source_type == "sec":
            entity = company or display_name
            if ticker:
                sec_specs[ticker] = (
                    entity,
                    tracking._slug(entity),
                    sector,
                    region,
                )
            continue
        if not re.match(r"^https?://", url, re.IGNORECASE):
            continue

        # Eastmoney uses a dedicated direct parser in crawl_official_with_tracking.
        if category == "media" and host.endswith("eastmoney.com"):
            continue

        keywords = tracking._source_keywords(raw, track_by_name)
        adapter = "rss" if source_type == "rss" else "generic_web"
        platform = "用户 RSS" if source_type == "rss" else display_name
        spec: dict[str, Any] = {
            "id": source_id,
            "name": display_name,
            "url": url,
            "sourceUrl": url,
            "adapter": adapter,
            "sourceCategory": category,
            "platform": platform,
            "sourceLevel": _source_level(category),
            "region": region,
            "sector": sector,
            "maxItems": 10,
            "keywords": keywords,
            "strictTitleKeywords": False,
            "enabled": True,
        }
        if company:
            spec["company"] = company
            spec["companySlug"] = tracking._slug(company)
        if ticker:
            spec["ticker"] = ticker
        specs.append(spec)

    return specs[:80], sec_specs


def _install_generic_adapter() -> None:
    original = tracking._install_runtime_overrides

    def install(
        merged: dict[str, Any],
        sec_specs: dict[str, tuple[str, str, str, str]],
        active_ids: set[str],
    ) -> None:
        original(merged, sec_specs, active_ids)
        original_crawl_source = tracking.crawler._crawl_config_source

        def crawl_source(
            spec: dict[str, Any], user_agent: str
        ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
            if spec.get("adapter") == "generic_web":
                return generic_web_sources.crawl_generic_source(
                    spec,
                    user_agent,
                    tracking.crawler,
                )
            return original_crawl_source(spec, user_agent)

        tracking.crawler._crawl_config_source = crawl_source

    tracking._install_runtime_overrides = install


def main() -> int:
    tracking._custom_sources = _custom_sources
    _install_generic_adapter()
    configure_crawler()
    _install_empty_sec_guard()
    return tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
