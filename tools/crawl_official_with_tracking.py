#!/usr/bin/env python3
"""Crawl the fixed company registry plus user-configured company/IR sources."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

try:  # Imported by tests as tools.crawl_official_with_tracking.
    from . import crawl_official_companies as official
    from .crawl_with_tracking import TRACKING_PATH, load_tracking
except ImportError:  # Executed directly with ``python tools/...``.
    import crawl_official_companies as official
    from crawl_with_tracking import TRACKING_PATH, load_tracking


USER_OFFICIAL_PREFIX = "official-user-"


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _slug(value: Any) -> str:
    text = _clean(value, 80).casefold()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text).strip("-")
    return text[:54] or "company"


def _root_url(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


def build_user_specs(tracking: dict[str, Any]) -> list[official.CompanySpec]:
    """Convert enabled company-homepage sources into official crawler specs.

    RSS sources stay in ``crawl_with_tracking.py`` because the official crawler is
    designed for company newsrooms and IR indexes. SEC sources are also handled
    by the main crawler's EDGAR adapter.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for raw in tracking.get("sources", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        if _clean(raw.get("sourceType"), 30) != "listing-search":
            continue
        url = _clean(raw.get("url"), 500)
        company = _clean(raw.get("company"), 80) or _clean(raw.get("name"), 80)
        if not company or not re.match(r"^https?://", url, flags=re.IGNORECASE):
            continue
        grouped[company.casefold()].append(raw)

    specs: list[official.CompanySpec] = []
    used_slugs: set[str] = set()
    for rows in grouped.values():
        first = rows[0]
        company = _clean(first.get("company"), 80) or _clean(first.get("name"), 80)
        slug_base = f"user-{_slug(company)}"
        slug = slug_base
        suffix = 2
        while slug in used_slugs:
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        used_slugs.add(slug)

        urls: list[str] = []
        aliases: list[str] = [company]
        keywords: list[str] = []
        ticker = ""
        for row in rows:
            url = official.normalize_url(_clean(row.get("url"), 500))
            if url and url not in urls:
                urls.append(url)
            ticker_value = _clean(row.get("ticker"), 30).upper()
            if ticker_value:
                ticker = ticker or ticker_value
                aliases.append(ticker_value)
            for keyword in row.get("keywords", []):
                cleaned = _clean(keyword, 80)
                if cleaned:
                    keywords.append(cleaned)

        homepage = _root_url(urls[0])
        region = _clean(first.get("region"), 20)
        if region not in {"中国", "美国", "全球"}:
            region = "全球"
        sector = _clean(first.get("sector"), 60) or "AI / AGI"
        sitemap_urls = tuple(
            dict.fromkeys(
                f"{_root_url(url).rstrip('/')}/sitemap.xml" for url in urls
            )
        )
        entity_aliases = tuple(dict.fromkeys([*aliases, *keywords]))
        specs.append(
            official.CompanySpec(
                slug=slug,
                name=company,
                region=region,
                sector=sector,
                homepage=homepage,
                news_urls=tuple(urls),
                sitemap_urls=sitemap_urls,
                aliases=tuple(dict.fromkeys(alias for alias in aliases if alias != company)),
                entity_aliases=entity_aliases,
                article_url_patterns=(
                    r"/(?:news|newsroom|press|media|blog|updates?)/",
                    r"/(?:investors?|investor-relations|ir)/",
                    r"/(?:announcements?|filings?|financials?)/",
                ),
                require_entity_match=False,
                max_items=6,
                max_candidate_links=18,
                max_age_days=730,
                request_timeout=10,
            )
        )
    return specs[:40]


def install_overrides(
    base_specs: list[official.CompanySpec], user_specs: list[official.CompanySpec]
) -> None:
    original_load_payload = official.load_existing_payload
    active_ids = {spec.source_id for spec in user_specs}

    def load_registry(
        path: Path = official.REGISTRY_PATH,
        catalog_path: Path = official.CATALOG_PATH,
    ) -> list[official.CompanySpec]:
        del path, catalog_path
        return [*base_specs, *user_specs]

    def load_payload(path: Path = official.OUTPUT_PATH) -> dict[str, Any]:
        payload = original_load_payload(path)
        payload["articles"] = [
            article
            for article in payload.get("articles", [])
            if not str(article.get("sourceId", "")).startswith(USER_OFFICIAL_PREFIX)
            or str(article.get("sourceId", "")) in active_ids
        ]
        payload["sourceStatus"] = [
            status
            for status in payload.get("sourceStatus", [])
            if not str(status.get("id", "")).startswith(USER_OFFICIAL_PREFIX)
            or str(status.get("id", "")) in active_ids
        ]
        return payload

    official.load_registry = load_registry
    official.load_existing_payload = load_payload


def main() -> int:
    base_specs = official.load_registry()
    tracking = load_tracking(TRACKING_PATH)
    user_specs = build_user_specs(tracking)
    install_overrides(base_specs, user_specs)
    print(
        json.dumps(
            {
                "fixedOfficialCompanies": len(base_specs),
                "userOfficialCompanies": len(user_specs),
            },
            ensure_ascii=False,
        )
    )
    return official.main()


if __name__ == "__main__":
    raise SystemExit(main())
