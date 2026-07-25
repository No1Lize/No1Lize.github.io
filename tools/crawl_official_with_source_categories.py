#!/usr/bin/env python3
"""Run the direct website crawler with category-aware source filtering.

Company sources are eligible for the generic direct website crawler. Media and
person sources stay in the category-aware feed/search crawler, except for
Eastmoney, which has a dedicated parser and listed-company attribution adapter
inside ``crawl_official_with_tracking``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

try:  # Imported by tests as tools.crawl_official_with_source_categories.
    from . import crawl_official_with_tracking as official_tracking
    from .crawl_with_source_categories import source_category
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_official_with_tracking as official_tracking
    from crawl_with_source_categories import source_category


def _is_supported_media_source(raw: dict[str, Any]) -> bool:
    name = official_tracking._clean(raw.get("name"), 80)
    url = official_tracking._clean(raw.get("url"), 500)
    host = (urlsplit(url).hostname or "").casefold()
    return "东方财富" in name or host == "eastmoney.com" or host.endswith(".eastmoney.com")


def _filtered_tracking(path=official_tracking.TRACKING_PATH) -> dict[str, Any]:
    payload = _original_load_tracking(path)
    filtered = dict(payload)
    filtered["sources"] = [
        raw
        for raw in payload.get("sources", [])
        if isinstance(raw, dict)
        and (
            source_category(raw) == "company"
            or (source_category(raw) == "media" and _is_supported_media_source(raw))
        )
    ]
    return filtered


_original_load_tracking = official_tracking.load_tracking


def main() -> int:
    official_tracking.load_tracking = _filtered_tracking
    return official_tracking.main()


if __name__ == "__main__":
    raise SystemExit(main())
