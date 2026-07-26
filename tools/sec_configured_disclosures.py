#!/usr/bin/env python3
"""Run SEC EDGAR enrichment with a verified configured-CIK registry first.

The SEC company-ticker index may reject shared CI runners. Current tracked US
companies therefore use CIKs verified from their SEC entity pages and stored in
``listed_company_disclosure_sources.json``. Dynamic ticker lookup remains a
fallback only for newly added companies that do not yet have a configured CIK.
"""

from __future__ import annotations

import argparse
import json
import re
from typing import Any, Callable

try:
    from . import crawl_listed_company_disclosures as base
    from . import sec_structured_disclosures as sec
except ImportError:
    import crawl_listed_company_disclosures as base
    import sec_structured_disclosures as sec


def normalize_cik(value: Any) -> str:
    digits = re.sub(r"\D", "", str(value or ""))
    if not digits:
        return ""
    try:
        numeric = int(digits)
    except ValueError:
        return ""
    return f"{numeric:010d}" if numeric > 0 else ""


def configured_ticker_ciks(
    listings: list[sec.USListing],
    config: dict[str, Any],
) -> tuple[dict[str, str], list[sec.USListing]]:
    registry = config.get("secCiks", {})
    registry = registry if isinstance(registry, dict) else {}
    resolved: dict[str, str] = {}
    missing: list[sec.USListing] = []
    for listing in listings:
        cik = normalize_cik(registry.get(listing.catalog_slug))
        if cik:
            resolved[listing.ticker.upper()] = cik
        else:
            missing.append(listing)
    return resolved, missing


def resolve_ticker_ciks(
    listings: list[sec.USListing],
    config: dict[str, Any],
    *,
    index_fetcher: Callable[..., dict[str, Any]] = sec.fetch_json,
) -> tuple[dict[str, str], dict[str, Any]]:
    resolved, missing = configured_ticker_ciks(listings, config)
    metadata: dict[str, Any] = {
        "configuredListingCount": len(listings) - len(missing),
        "dynamicLookupAttempted": bool(missing),
        "dynamicResolvedCount": 0,
        "dynamicLookupErrors": [],
    }
    if not missing:
        return resolved, metadata

    settings = config.get("settings", {})
    try:
        index_payload = index_fetcher(
            sec.TICKER_INDEX_URL,
            timeout=int(settings.get("requestTimeout", 18)),
            attempts=int(settings.get("requestAttempts", 2)),
        )
        dynamic = sec.parse_ticker_index(index_payload)
    except Exception as exc:  # noqa: BLE001 - unresolved listings remain explicit.
        dynamic = {}
        metadata["dynamicLookupErrors"] = [f"{type(exc).__name__}:{exc}"]

    for listing in missing:
        cik = normalize_cik(dynamic.get(listing.ticker.upper()))
        if cik:
            resolved[listing.ticker.upper()] = cik
            metadata["dynamicResolvedCount"] += 1
    return resolved, metadata


def apply_registry_metadata(
    snapshot: dict[str, Any],
    listings: list[sec.USListing],
    ticker_ciks: dict[str, str],
    registry_metadata: dict[str, Any],
) -> dict[str, Any]:
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    configured_slugs = {
        listing.catalog_slug
        for listing in listings
        if listing.ticker.upper() in ticker_ciks
    }
    statuses = [
        status
        for status in result.get("sourceStatus", [])
        if isinstance(status, dict)
    ]
    listing_by_id = {listing.source_id: listing for listing in listings}
    for status in statuses:
        listing = listing_by_id.get(str(status.get("id", "")))
        if not listing:
            continue
        status["cikSource"] = (
            "configured-official-registry"
            if listing.catalog_slug in configured_slugs
            else "dynamic-sec-ticker-index"
        )
    result["sourceStatus"] = statuses
    metadata = result.get("secStructured")
    metadata = dict(metadata) if isinstance(metadata, dict) else {}
    metadata["cikRegistry"] = registry_metadata
    result["secStructured"] = metadata
    return result


def validate_registry_coverage(
    snapshot: dict[str, Any],
    listings: list[sec.USListing],
) -> list[str]:
    errors = sec.validate_enrichment(snapshot, listings, require_events=True)
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    for listing in listings:
        status = statuses.get(listing.source_id, {})
        if not status.get("cikSource"):
            errors.append(f"SEC CIK source missing: {listing.source_id}")
        if int(status.get("accepted", 0) or 0) <= 0:
            errors.append(f"SEC source accepted no filings: {listing.source_id}")
    metadata = snapshot.get("secStructured", {})
    registry = metadata.get("cikRegistry", {}) if isinstance(metadata, dict) else {}
    if not isinstance(registry, dict):
        errors.append("SEC CIK registry metadata missing")
    elif int(registry.get("configuredListingCount", -1)) < len(listings):
        unresolved = [
            listing.source_id
            for listing in listings
            if not statuses.get(listing.source_id, {}).get("cikResolved")
        ]
        if unresolved:
            errors.append("unresolved SEC listings: " + ", ".join(unresolved))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    args = parser.parse_args()

    listings = sec.load_us_listings()
    if args.check:
        snapshot = base.load_previous(sec.OUTPUT_PATH)
        errors = validate_registry_coverage(snapshot, listings)
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {
                    "passed": True,
                    "listedCompanyCount": len(listings),
                    "acceptedEventCount": snapshot.get("secStructured", {}).get(
                        "acceptedEventCount", 0
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0

    config = base.load_config()
    settings = config["settings"]
    ticker_ciks, registry_metadata = resolve_ticker_ciks(listings, config)
    snapshot = base.load_previous(sec.OUTPUT_PATH)
    enriched = sec.enrich_snapshot(snapshot, listings, ticker_ciks, settings)
    enriched = apply_registry_metadata(
        enriched,
        listings,
        ticker_ciks,
        registry_metadata,
    )
    errors = (
        validate_registry_coverage(enriched, listings)
        if args.require_events
        else sec.validate_enrichment(enriched, listings)
    )
    if errors:
        raise SystemExit("; ".join(errors))
    sec.write_snapshot(enriched, sec.OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
