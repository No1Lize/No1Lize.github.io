#!/usr/bin/env python3
"""Entity attribution for concrete Eastmoney article pages.

The tracking admin owns the listed-company watchlist. When the repository config
has not persisted that optional array yet, the website intentionally falls back
to the IPO catalog; this module mirrors the same rule for the Python crawler.
Attribution uses ranked, conservative evidence: headline entities first,
structured Eastmoney quote links second, then a unique company in the extracted
lead paragraphs. Ambiguous comparison and industry stories remain unassigned.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, unquote, urlsplit

try:  # Imported by tests as tools.eastmoney_entities.
    from .crawl_articles import ROOT, clean_text, infer_company, infer_sector
except ImportError:  # Executed directly with ``python tools/...``.
    from crawl_articles import ROOT, clean_text, infer_company, infer_sector


CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
EASTMONEY_ARTICLE_PATH = re.compile(
    r"/a/20\d{12,}\.html$", flags=re.IGNORECASE
)
HREF_PATTERN = re.compile(
    r"\bhref\s*=\s*([\"'])(.*?)\1", flags=re.IGNORECASE | re.DOTALL
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


def _latin_alias_match(alias: str, text: str) -> bool:
    return bool(
        re.search(
            rf"(?<![a-z0-9]){re.escape(alias.casefold())}(?![a-z0-9])",
            text.casefold(),
        )
    )


def _name_match(alias: str, text: str) -> bool:
    cleaned = clean_text(alias)
    if not cleaned:
        return False
    if re.fullmatch(r"[A-Za-z0-9 .&+_-]+", cleaned):
        return _latin_alias_match(cleaned, text)
    return cleaned in text


def _ticker_variants(ticker: str) -> set[str]:
    cleaned = re.sub(r"\s+", "", str(ticker or "")).upper().strip("$()[]（）【】")
    cleaned = re.sub(r"\.(?:SH|SZ|BJ|HK|US)$", "", cleaned)
    if re.fullmatch(r"(?:SH|SZ|BJ|HK)\d+", cleaned):
        cleaned = re.sub(r"^(?:SH|SZ|BJ|HK)", "", cleaned)
    variants = {cleaned} if cleaned else set()
    if cleaned.isdigit():
        variants.add(cleaned.lstrip("0") or "0")
    return variants


def _ticker_match(ticker: str, text: str) -> bool:
    variants = _ticker_variants(ticker)
    if not variants:
        return False
    canonical = max(variants, key=len)
    escaped = re.escape(canonical)
    if canonical.isdigit():
        # A bare six-digit number can be a date, amount or article id. Numeric
        # tickers require an explicit stock/code marker, market prefix or brackets.
        explicit_patterns = (
            rf"(?:股票|证券|股票代码|证券代码|代码|港股|沪市|深市|科创板|创业板)"
            rf"\s*[:：]?\s*(?<!\d){escaped}(?!\d)",
            rf"(?:SH|SZ|BJ|HK)\s*[.:：-]?\s*(?<!\d){escaped}(?!\d)",
            rf"[\(\[（【]\s*{escaped}\s*[\)\]）】]",
        )
        return any(
            re.search(pattern, text, flags=re.IGNORECASE)
            for pattern in explicit_patterns
        )
    explicit_patterns = (
        rf"\${escaped}(?![A-Z0-9])",
        rf"(?:NASDAQ|NYSE|AMEX|Ticker|股票代码|证券代码|代码)"
        rf"\s*[:：]?\s*{escaped}(?![A-Z0-9])",
        rf"[\(\[（【]\s*{escaped}\s*[\)\]）】]",
    )
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in explicit_patterns)


def _entity_matches_text(entity: dict[str, str], text: str) -> bool:
    aliases = (entity.get("name", ""), entity.get("englishName", ""))
    return any(_name_match(alias, text) for alias in aliases if alias) or _ticker_match(
        entity.get("ticker", ""), text
    )


def _quote_tickers_from_url(raw_url: str) -> set[str]:
    href = html.unescape(raw_url).strip()
    if href.startswith("//"):
        href = f"https:{href}"
    parts = urlsplit(href)
    host = (parts.hostname or "").casefold()
    if not host.endswith("eastmoney.com"):
        return set()

    path = unquote(parts.path)
    found: set[str] = set()
    path_patterns = (
        r"/unify/r/\d+\.([A-Za-z0-9.-]{1,20})$",
        r"/(?:sh|sz|bj)(\d{6})(?:\.html)?$",
        r"/hk/(\d{4,5})(?:\.html)?$",
        r"/us/([A-Za-z][A-Za-z0-9.-]{0,14})(?:\.html)?$",
    )
    for pattern in path_patterns:
        match = re.search(pattern, path, flags=re.IGNORECASE)
        if match:
            found.update(_ticker_variants(match.group(1)))

    query = parse_qs(parts.query)
    for key in ("secid", "code", "stockcode", "symbol"):
        for raw_value in query.get(key, []):
            value = raw_value.rsplit(".", 1)[-1]
            if re.fullmatch(r"[A-Za-z0-9.-]{1,20}", value):
                found.update(_ticker_variants(value))
    return found


def _extract_eastmoney_linked_ticker_groups(
    body: str,
) -> set[frozenset[str]]:
    """Return distinct securities, preserving equivalent ticker variants."""

    groups: set[frozenset[str]] = set()
    for match in HREF_PATTERN.finditer(body or ""):
        variants = _quote_tickers_from_url(match.group(2))
        if variants:
            groups.add(frozenset(variants))
    return groups


def extract_eastmoney_linked_tickers(body: str) -> set[str]:
    """Return ticker variants carried by structured Eastmoney quote/data links."""

    linked: set[str] = set()
    for group in _extract_eastmoney_linked_ticker_groups(body):
        linked.update(group)
    return linked


def _entity_matches_linked_ticker(
    entity: dict[str, str], linked_tickers: set[str]
) -> bool:
    return bool(_ticker_variants(entity.get("ticker", "")) & linked_tickers)


def _market_region(market: str) -> str:
    return "美国" if market == "美股" else "中国"


def _apply_entity(updated: dict[str, Any], entity: dict[str, str]) -> dict[str, Any]:
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


def _clear_primary_entity(updated: dict[str, Any]) -> None:
    updated["company"] = "科技产业"
    updated.pop("companySlug", None)
    updated.pop("ticker", None)
    updated.pop("market", None)


def attribute_eastmoney_article(
    article: dict[str, Any],
    entities: Iterable[dict[str, str]],
    page_body: str = "",
) -> dict[str, Any]:
    """Attribute a detail article using conservative, ranked entity evidence."""

    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_url = _clean(source.get("url"), 500)
    if not is_eastmoney_article_url(source_url):
        return article

    updated = dict(article)
    entity_list = list(entities)
    title = clean_text(str(updated.get("title", "")))
    summary = clean_text(str(updated.get("summary", "")))

    title_matches = [
        entity for entity in entity_list if _entity_matches_text(entity, title)
    ]
    if len(title_matches) == 1:
        return _apply_entity(updated, title_matches[0])
    if len(title_matches) > 1:
        _clear_primary_entity(updated)
        updated["sector"] = infer_sector(
            title, summary, str(updated.get("sector") or "AI / AGI")
        )
        return updated

    linked_groups = _extract_eastmoney_linked_ticker_groups(page_body)
    linked_tickers = {variant for group in linked_groups for variant in group}
    linked_matches = [
        entity
        for entity in entity_list
        if _entity_matches_linked_ticker(entity, linked_tickers)
    ]
    if len(linked_groups) == 1 and len(linked_matches) == 1:
        return _apply_entity(updated, linked_matches[0])
    if len(linked_matches) > 1:
        _clear_primary_entity(updated)
        updated["sector"] = infer_sector(
            title, summary, str(updated.get("sector") or "AI / AGI")
        )
        return updated

    summary_matches = [
        entity for entity in entity_list if _entity_matches_text(entity, summary)
    ]
    if len(summary_matches) == 1:
        return _apply_entity(updated, summary_matches[0])
    if len(summary_matches) > 1:
        _clear_primary_entity(updated)
        updated["sector"] = infer_sector(
            title, summary, str(updated.get("sector") or "AI / AGI")
        )
        return updated

    # No tracked company matched. Reuse the crawler's conservative core-company
    # title map, then infer only the sector from the extracted lead paragraphs.
    inferred_name, inferred_slug, inferred_region = infer_company(title, "")
    if inferred_slug or inferred_name != "科技产业":
        updated["company"] = inferred_name
        if inferred_slug:
            updated["companySlug"] = inferred_slug
        else:
            updated.pop("companySlug", None)
        if inferred_region:
            updated["region"] = inferred_region
    else:
        _clear_primary_entity(updated)

    updated["sector"] = infer_sector(
        title,
        summary,
        str(updated.get("sector") or "AI / AGI"),
    )
    return updated
