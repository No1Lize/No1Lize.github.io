#!/usr/bin/env python3
"""Entity attribution for concrete Eastmoney article pages.

The tracking admin owns the listed-company watchlist. When the repository config
has not persisted that optional array yet, the website intentionally falls back
to the IPO catalog; this module mirrors the same rule for the Python crawler.
Only unambiguous title matches are accepted so a comparison article mentioning
several companies is never assigned to whichever alias happens to appear first.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

try:  # Imported by tests as tools.eastmoney_entities.
    from .crawl_articles import ROOT, clean_text, infer_company, infer_sector
except ImportError:  # Executed directly with ``python tools/...``.
    from crawl_articles import ROOT, clean_text, infer_company, infer_sector


CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
EASTMONEY_ARTICLE_PATH = re.compile(
    r"/a/20\d{12,}\.html$", flags=re.IGNORECASE
)
VALID_MARKETS = {"A股", "港股", "美股"}


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _normalized_host(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    return host[4:] if host.startswith("www.") else host


def is_eastmoney_article_url(url: str) -> bool:
    parts = urlsplit(_clean(url, 500))
    return _normalized_host(url).endswith("eastmoney.com") and bool(
        EASTMONEY_ARTICLE_PATH.search(parts.path)
    )


def _catalog_sections(body: str) -> tuple[str, str]:
    companies = re.search(
        r"export\s+const\s+companies\s*:\s*Company\[\]\s*=\s*\[(.*?)\n\];",
        body,
        flags=re.DOTALL,
    )
    listed = re.search(
        r"export\s+const\s+ipoCompanies\s*:\s*IpoCompany\[\]\s*=\s*\[(.*?)\n\];",
        body,
        flags=re.DOTALL,
    )
    return (
        companies.group(1) if companies else "",
        listed.group(1) if listed else "",
    )


def _catalog_entities(path: Path = CATALOG_PATH) -> list[dict[str, str]]:
    body = path.read_text(encoding="utf-8")
    companies_section, listed_section = _catalog_sections(body)

    english_by_slug: dict[str, str] = {}
    company_pattern = re.compile(
        r'\{\s*slug:"([^"]+)",\s*name:"([^"]+)",'
        r'(?:\s*englishName:"([^"]+)",)?\s*region:"[^"]+",'
        r'\s*sector:"[^"]+"'
    )
    for match in company_pattern.finditer(companies_section):
        if match.group(3):
            english_by_slug[match.group(1)] = match.group(3)

    listed_pattern = re.compile(
        r'\{\s*slug:"([^"]+)",\s*name:"([^"]+)",'
        r'\s*market:"([^"]+)",\s*ticker:"([^"]+)",'
        r'\s*sector:"([^"]+)"'
    )
    entities: list[dict[str, str]] = []
    for match in listed_pattern.finditer(listed_section):
        slug, name, market, ticker, sector = match.groups()
        entities.append(
            {
                "id": f"catalog-{slug}",
                "name": name,
                "ticker": ticker.upper(),
                "market": market,
                "sector": sector,
                "catalogSlug": slug,
                "englishName": english_by_slug.get(slug, ""),
            }
        )
    return entities


def _tracking_entities(tracking: dict[str, Any]) -> list[dict[str, str]]:
    raw_items = tracking.get("listedCompanies", [])
    if not isinstance(raw_items, list) or not raw_items:
        return []

    entities: list[dict[str, str]] = []
    for index, raw in enumerate(raw_items):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = _clean(raw.get("name"), 80)
        ticker = _clean(raw.get("ticker"), 30).upper().replace(" ", "")
        market = _clean(raw.get("market"), 20)
        if not name or not ticker or market not in VALID_MARKETS:
            continue
        catalog_slug = _clean(raw.get("catalogSlug"), 80)
        entities.append(
            {
                "id": _clean(raw.get("id"), 100)
                or f"listed-{market}-{ticker}-{index + 1}",
                "name": name,
                "ticker": ticker,
                "market": market,
                "sector": _clean(raw.get("sector"), 60) or "未分类",
                "catalogSlug": catalog_slug,
                "englishName": "",
            }
        )
    return entities


def build_listed_entity_index(
    tracking: dict[str, Any], catalog_path: Path = CATALOG_PATH
) -> list[dict[str, str]]:
    """Return the active watchlist using the frontend's catalog fallback rule."""

    catalog = _catalog_entities(catalog_path)
    configured = _tracking_entities(tracking)
    if not configured:
        return catalog

    catalog_by_slug = {
        entity["catalogSlug"]: entity for entity in catalog if entity["catalogSlug"]
    }
    catalog_by_key = {
        f'{entity["market"]}:{entity["ticker"]}': entity for entity in catalog
    }
    resolved: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in configured:
        fallback = (
            catalog_by_slug.get(item["catalogSlug"])
            if item["catalogSlug"]
            else catalog_by_key.get(f'{item["market"]}:{item["ticker"]}')
        )
        merged = {
            **(fallback or {}),
            **item,
            "englishName": item.get("englishName")
            or (fallback or {}).get("englishName", ""),
        }
        key = f'{merged["market"]}:{merged["ticker"]}'
        if key not in seen:
            resolved.append(merged)
            seen.add(key)
    return resolved


def _latin_alias_match(alias: str, title: str) -> bool:
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])",
            title.casefold(),
        )
    )


def _name_match(alias: str, title: str) -> bool:
    cleaned = clean_text(alias)
    if not cleaned:
        return False
    if re.fullmatch(r"[A-Za-z0-9 .&+_-]+", cleaned):
        return _latin_alias_match(cleaned, title)
    return cleaned in title


def _ticker_match(ticker: str, title: str) -> bool:
    cleaned = re.sub(r"\s+", "", ticker).upper()
    if not cleaned:
        return False
    escaped = re.escape(cleaned)
    if cleaned.isdigit():
        return bool(
            re.search(
                rf"(?:股票|证券|代码|港股|沪市|深市|科创板|创业板)?"
                rf"\s*[:：]?\s*(?<!\d){escaped}(?!\d)",
                title,
                flags=re.IGNORECASE,
            )
        )
    explicit_patterns = (
        rf"\${escaped}(?![A-Z0-9])",
        rf"(?:NASDAQ|NYSE|AMEX|Ticker|股票代码|证券代码|代码)"
        rf"\s*[:：]?\s*{escaped}(?![A-Z0-9])",
        rf"[\(\[（【]\s*{escaped}\s*[\)\]）】]",
    )
    return any(re.search(pattern, title, flags=re.IGNORECASE) for pattern in explicit_patterns)


def _entity_matches_title(entity: dict[str, str], title: str) -> bool:
    aliases = (entity.get("name", ""), entity.get("englishName", ""))
    return any(_name_match(alias, title) for alias in aliases if alias) or _ticker_match(
        entity.get("ticker", ""), title
    )


def _market_region(market: str) -> str:
    return "美国" if market == "美股" else "中国"


def attribute_eastmoney_article(
    article: dict[str, Any], entities: Iterable[dict[str, str]]
) -> dict[str, Any]:
    """Attribute an Eastmoney article only when the title has one clear entity."""

    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_url = _clean(source.get("url"), 500)
    if not is_eastmoney_article_url(source_url):
        return article

    updated = dict(article)
    title = clean_text(str(updated.get("title", "")))
    summary = clean_text(str(updated.get("summary", "")))
    matches = [entity for entity in entities if _entity_matches_title(entity, title)]

    if len(matches) == 1:
        entity = matches[0]
        updated["company"] = entity["name"]
        updated["ticker"] = entity["ticker"]
        updated["market"] = entity["market"]
        updated["region"] = _market_region(entity["market"])
        if entity.get("sector") and entity["sector"] != "未分类":
            updated["sector"] = entity["sector"]
        if entity.get("catalogSlug"):
            updated["companySlug"] = entity["catalogSlug"]
        else:
            updated.pop("companySlug", None)
        return updated

    # Multiple tracked companies in one headline are comparison/industry stories.
    # With no tracked match, reuse the crawler's conservative core-company map.
    inferred_name, inferred_slug, inferred_region = infer_company(title, "")
    if len(matches) > 1:
        updated["company"] = "科技产业"
        updated.pop("companySlug", None)
        updated.pop("ticker", None)
        updated.pop("market", None)
    elif inferred_slug or inferred_name != "科技产业":
        updated["company"] = inferred_name
        if inferred_slug:
            updated["companySlug"] = inferred_slug
        else:
            updated.pop("companySlug", None)
        if inferred_region:
            updated["region"] = inferred_region
    else:
        updated["company"] = "科技产业"
        updated.pop("companySlug", None)

    updated["sector"] = infer_sector(
        title,
        summary,
        str(updated.get("sector") or "AI / AGI"),
    )
    return updated
