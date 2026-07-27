#!/usr/bin/env python3
"""Publish verified official US filing baselines without network dependency.

This deterministic publisher is used to bootstrap every enabled US-listed
company into the formal disclosure snapshot. Live company-IR crawling remains
responsible for adding newer filings in subsequent refreshes.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    from . import crawl_listed_company_disclosures as base
    from . import sec_structured_disclosures as sec
    from . import us_ir_baseline_disclosures as baselines
    from . import us_ir_sec_disclosures as ir
except ImportError:
    import crawl_listed_company_disclosures as base
    import sec_structured_disclosures as sec
    import us_ir_baseline_disclosures as baselines
    import us_ir_sec_disclosures as ir

OUTPUT_PATH = Path(__file__).resolve().parents[1] / "public" / "data" / "listed_company_disclosures.json"


def build_snapshot(previous: dict[str, Any] | None = None) -> dict[str, Any]:
    previous = previous or base.load_previous(OUTPUT_PATH)
    result = json.loads(json.dumps(previous, ensure_ascii=False))
    rows = sec.load_us_listings()
    config = base.load_config()
    sources = ir.load_ir_sources(rows, config)
    registry = baselines.load_baselines(rows, config)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    companies = result.setdefault("companies", {})
    existing_statuses = [
        status
        for status in result.get("sourceStatus", [])
        if isinstance(status, dict)
        and not str(status.get("id", "")).startswith("us-ir-disclosure-")
        and not str(status.get("id", "")).startswith("sec-disclosure-")
    ]
    statuses = list(existing_statuses)

    for listing in rows:
        source = sources[listing.catalog_slug]
        event = baselines.baseline_event(
            listing,
            source,
            registry[listing.catalog_slug],
        )
        company = companies.setdefault(
            listing.catalog_slug,
            {
                "slug": listing.catalog_slug,
                "name": listing.name,
                "updatedAt": generated_at,
                "status": "partial",
                "listings": [],
                "events": [],
            },
        )
        if not isinstance(company, dict):
            raise ValueError(f"invalid company profile object: {listing.catalog_slug}")
        marker = {
            "market": "美股",
            "ticker": listing.ticker,
            "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
            "listingRole": listing.listing_role,
        }
        listing_rows = company.setdefault("listings", [])
        if marker not in listing_rows:
            listing_rows.append(marker)
        existing_events = [
            row for row in company.get("events", []) if isinstance(row, dict)
        ]
        company["events"] = ir._merge_events(existing_events, [event], 60)
        company["updatedAt"] = generated_at
        company["status"] = "ok"
        company["officialEventCount"] = sum(
            not bool(row.get("fallback")) for row in company["events"]
        )
        company["fallbackEventCount"] = sum(
            bool(row.get("fallback")) for row in company["events"]
        )
        statuses.append(
            {
                "id": f"us-ir-disclosure-{listing.catalog_slug}-{listing.ticker.casefold()}",
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": "美股",
                "ticker": listing.ticker,
                "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
                "provider": baselines.PROVIDER,
                "sourceName": source.name,
                "sourceUrl": source.url,
                "sourceHost": source.host,
                "status": "ok",
                "attempted": True,
                "scanned": 1,
                "accepted": 1,
                "liveAccepted": 0,
                "baselineAccepted": 1,
                "baselineUrl": event["source"]["url"],
                "discoveryModes": ["verified-official-baseline"],
                "errors": [],
            }
        )

    result["generatedAt"] = generated_at
    result["companies"] = companies
    result["sourceStatus"] = statuses
    result["companyCount"] = len(companies)
    result["eventCount"] = sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    result.pop("secStructured", None)
    result["usIrStructured"] = {
        "schemaVersion": 1,
        "provider": "official-company-ir-sec-filings",
        "attemptedListingCount": len(rows),
        "acceptedEventCount": len(rows),
        "verifiedBaselineCount": len(rows),
        "directSecAccess": "blocked-by-sec-for-shared-ci-ip",
        "retentionPolicy": "live-official-discovery-plus-verified-baseline",
    }
    errors = baselines.validate_snapshot(result, rows)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def write_snapshot(snapshot: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    return ir.write_snapshot(snapshot, path)


def main() -> int:
    snapshot = build_snapshot(base.load_previous(OUTPUT_PATH))
    write_snapshot(snapshot, OUTPUT_PATH)
    print(
        json.dumps(
            {
                "companyCount": snapshot.get("companyCount", 0),
                "eventCount": snapshot.get("eventCount", 0),
                "verifiedBaselineCount": snapshot.get("usIrStructured", {}).get(
                    "verifiedBaselineCount", 0
                ),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
