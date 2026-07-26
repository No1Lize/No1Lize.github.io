#!/usr/bin/env python3
"""Add official-domain search fallback to US investor-relations filing refresh.

Some investor-relations filing lists are rendered client-side and therefore do
not expose rows in the initial HTML. The fallback searches only the configured
company IR host, opens result detail pages on that same official host, and
extracts Form, Filing Date and Description from those detail pages.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any
from urllib.parse import quote_plus

try:
    from . import crawl_listed_company_disclosures as base
    from . import sec_structured_disclosures as sec
    from . import us_ir_sec_disclosures as ir
except ImportError:
    import crawl_listed_company_disclosures as base
    import sec_structured_disclosures as sec
    import us_ir_sec_disclosures as ir

PROVIDER = "official-company-ir-domain-search"
DETAIL_DESCRIPTION = re.compile(
    r"Form\s+Description\s+(.*?)\s+(?:Filing\s+Group|Company|Issuer|Filing\s+Formats)",
    flags=re.IGNORECASE | re.DOTALL,
)
DETAIL_DOCUMENT_DATE = re.compile(
    r"Document\s+Date\s+([^|]{4,40}?)(?=\s+(?:Form\s+Description|Filing\s+Group|Company|Issuer|$))",
    flags=re.IGNORECASE,
)


def bing_web_rss(query: str) -> str:
    return "https://www.bing.com/search?format=rss&q=" + quote_plus(query)


def search_query(listing: sec.USListing, source: ir.IRSource) -> str:
    forms = (
        '"10-K" OR "10-Q" OR "8-K" OR "20-F" OR "6-K" OR '
        '"F-1" OR "S-1" OR "S-3" OR "F-3" OR "424B4" OR "DEF 14A"'
    )
    return (
        f"site:{source.host} ({forms}) "
        f'("{listing.name}" OR "{listing.ticker}")'
    )


def _detail_description(text: str, candidate: base.Candidate, form: str) -> str:
    match = DETAIL_DESCRIPTION.search(text)
    if match:
        value = base.clean_text(match.group(1), 500)
        if value:
            return value
    fallback = base.clean_text(
        f"{candidate.title} {candidate.summary}",
        500,
    )
    fallback = re.sub(r"^\S+\s*\|\s*", "", fallback)
    fallback = re.sub(rf"\b{re.escape(form)}\b", " ", fallback, flags=re.I)
    fallback = re.sub(r"\s+", " ", fallback).strip(" |_-—")
    return fallback or f"Official investor-relations filing detail for SEC Form {form}."


def detail_event(
    listing: sec.USListing,
    source: ir.IRSource,
    candidate: base.Candidate,
    body: str,
) -> dict[str, Any] | None:
    host = ir.normalized_host(candidate.url)
    if host != source.host and not (host == "sec.gov" or host.endswith(".sec.gov")):
        return None
    text = base.clean_text(body, 30_000)
    form = ir.extract_form(f"{candidate.title} {candidate.summary} {text}")
    document_type = sec.FORM_TYPES.get(form)
    if not document_type:
        return None
    published_at = ir.extract_date(text) or candidate.published_at
    if not published_at:
        return None
    try:
        date.fromisoformat(published_at)
    except ValueError:
        return None
    description = _detail_description(text, candidate, form)
    document_match = DETAIL_DOCUMENT_DATE.search(text)
    document_date = (
        ir.extract_date(document_match.group(1)) if document_match else ""
    )
    digest = base.hashlib.sha256(candidate.url.encode("utf-8")).hexdigest()[:18]
    summary_parts = [
        f"Ticker {listing.ticker}",
        f"Form {form}",
        f"Filed {published_at}",
        f"Document date {document_date}" if document_date else "",
        f"Official filing detail maintained by {source.name}",
    ]
    return {
        "id": f"disclosure-{listing.catalog_slug}-{digest}",
        "companySlug": listing.catalog_slug,
        "companyName": listing.name,
        "market": "美股",
        "ticker": listing.ticker,
        "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
        "listingRole": listing.listing_role,
        "publishedAt": published_at,
        "documentType": document_type,
        "title": f"{listing.name} SEC Form {form} — {description}",
        "summary": " · ".join(part for part in summary_parts if part),
        "source": {
            "name": source.name,
            "url": candidate.url,
            "level": "监管文件",
        },
        "discoveredVia": PROVIDER,
        "fallback": False,
        "regulatoryMirror": True,
        "form": form,
        "documentDate": document_date,
    }


def search_official_details(
    listing: sec.USListing,
    source: ir.IRSource,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeout = int(settings.get("requestTimeout", 18))
    attempts = int(settings.get("requestAttempts", 2))
    limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    cutoff = date.today() - timedelta(days=int(settings.get("maxAgeDays", 1095)))
    errors: list[str] = []
    candidates: list[base.Candidate] = []
    query = search_query(listing, source)
    try:
        body = ir.fetch_text(
            bing_web_rss(query),
            timeout=timeout,
            attempts=attempts,
        )
        candidates = base.parse_rss(body, PROVIDER)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"search:{type(exc).__name__}:{exc}")

    accepted: dict[str, dict[str, Any]] = {}
    scanned = 0
    for candidate in candidates[: max(limit * 3, 30)]:
        host = ir.normalized_host(candidate.url)
        if host != source.host and not (host == "sec.gov" or host.endswith(".sec.gov")):
            continue
        scanned += 1
        try:
            detail_body = ir.fetch_text(
                candidate.url,
                timeout=timeout,
                attempts=attempts,
            )
            event = detail_event(listing, source, candidate, detail_body)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"detail:{type(exc).__name__}:{exc}")
            continue
        if not event:
            continue
        try:
            if date.fromisoformat(event["publishedAt"]) < cutoff:
                continue
        except ValueError:
            continue
        accepted[event["source"]["url"]] = event
        if len(accepted) >= limit:
            break
    rows = sorted(
        accepted.values(),
        key=lambda event: (event["publishedAt"], event["id"]),
        reverse=True,
    )[:limit]
    return rows, {
        "provider": PROVIDER,
        "query": query,
        "searchResults": len(candidates),
        "scanned": scanned,
        "accepted": len(rows),
        "errors": errors[:20],
    }


def crawl_source(
    listing: sec.USListing,
    source: ir.IRSource,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct_rows, status = _ORIGINAL_CRAWL_SOURCE(listing, source, settings)
    remaining = max(
        0,
        min(int(settings.get("maxItemsPerListing", 18)), 30) - len(direct_rows),
    )
    if remaining <= 0:
        status["discoveryModes"] = ["direct-list"]
        return direct_rows, status

    search_rows, search_status = search_official_details(listing, source, settings)
    merged = ir._merge_events(
        direct_rows,
        search_rows,
        max(1, min(int(settings.get("maxItemsPerListing", 18)), 30)),
    )
    status["directAccepted"] = len(direct_rows)
    status["searchAccepted"] = len(search_rows)
    status["searchScanned"] = search_status["scanned"]
    status["searchResults"] = search_status["searchResults"]
    status["searchQuery"] = search_status["query"]
    status["searchErrors"] = search_status["errors"]
    status["accepted"] = len(merged)
    status["status"] = "ok" if merged else "error"
    status["discoveryModes"] = [
        mode
        for mode, enabled in (
            ("direct-list", bool(direct_rows)),
            ("official-domain-search", bool(search_rows)),
        )
        if enabled
    ]
    return merged, status


_ORIGINAL_CRAWL_SOURCE = ir.crawl_source
ir.crawl_source = crawl_source


def main() -> int:
    return ir.main()


if __name__ == "__main__":
    raise SystemExit(main())
