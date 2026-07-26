#!/usr/bin/env python3
"""Enrich every enabled US-listed company through SEC EDGAR.

The crawler resolves tickers through SEC's public company-ticker index, reads
structured submission metadata, and publishes only original EDGAR filing URLs.
It stores metadata and short factual summaries, not full filing text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

try:
    from . import crawl_listed_company_disclosures as base
except ImportError:
    import crawl_listed_company_disclosures as base

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
TICKER_INDEX_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_ROOT = "https://data.sec.gov/submissions/"
ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data"
PROVIDER = "sec-edgar-submissions"
DEFAULT_USER_AGENT = (
    "No1LizeResearchBot/1.0 No1Lize@users.noreply.github.com "
    "https://github.com/No1Lize/No1Lize.github.io"
)
FORM_TYPES = {
    "10-K": "定期报告与业绩",
    "10-K/A": "定期报告与业绩",
    "10-Q": "定期报告与业绩",
    "10-Q/A": "定期报告与业绩",
    "20-F": "定期报告与业绩",
    "20-F/A": "定期报告与业绩",
    "8-K": "重大经营与风险",
    "8-K/A": "重大经营与风险",
    "6-K": "重大经营与风险",
    "6-K/A": "重大经营与风险",
    "S-1": "招股与上市",
    "S-1/A": "招股与上市",
    "F-1": "招股与上市",
    "F-1/A": "招股与上市",
    "424B4": "招股与上市",
    "S-3": "证券发行与融资",
    "S-3/A": "证券发行与融资",
    "F-3": "证券发行与融资",
    "F-3/A": "证券发行与融资",
    "424B2": "证券发行与融资",
    "424B3": "证券发行与融资",
    "424B5": "证券发行与融资",
    "424B7": "证券发行与融资",
    "DEF 14A": "公司治理与股东事项",
    "PRE 14A": "公司治理与股东事项",
    "SC 13D": "股权变动",
    "SC 13D/A": "股权变动",
    "SC 13G": "股权变动",
    "SC 13G/A": "股权变动",
}
FORM_LABELS = {
    "定期报告与业绩": "periodic financial report",
    "重大经营与风险": "current report and material business update",
    "招股与上市": "registration statement or IPO prospectus",
    "证券发行与融资": "securities offering and financing filing",
    "公司治理与股东事项": "proxy and shareholder governance filing",
    "股权变动": "beneficial ownership filing",
}
ALLOWED_SEC_DOCUMENT_TYPES = set(FORM_LABELS)


@dataclass(frozen=True)
class USListing:
    catalog_slug: str
    name: str
    ticker: str
    sector: str
    listing_role: str = "primary"

    @property
    def source_id(self) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", self.catalog_slug.casefold()).strip("-")
        return f"sec-disclosure-{slug}-{self.ticker.casefold()}"


def clean(value: Any, limit: int = 1000) -> str:
    return base.clean_text(value, limit)


def load_us_listings(path: Path = TRACKING_PATH) -> list[USListing]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows: list[USListing] = []
    seen: set[tuple[str, str]] = set()
    for raw in payload.get("listedCompanies", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        if clean(raw.get("market"), 20) != "美股":
            continue
        ticker = re.sub(r"[^A-Z0-9.-]", "", str(raw.get("ticker", "")).upper())
        listing = USListing(
            catalog_slug=clean(raw.get("catalogSlug"), 80),
            name=clean(raw.get("name"), 160),
            ticker=ticker,
            sector=clean(raw.get("sector"), 80),
        )
        marker = (listing.catalog_slug, listing.ticker)
        if not all((listing.catalog_slug, listing.name, listing.ticker, listing.sector)):
            raise ValueError(f"incomplete US listed-company row: {raw}")
        if marker in seen:
            continue
        seen.add(marker)
        rows.append(listing)
    return rows


def _decode_json(payload: bytes, charset: str | None = None) -> dict[str, Any]:
    for encoding in [charset, "utf-8"]:
        if not encoding:
            continue
        try:
            value = json.loads(payload.decode(encoding))
            return value if isinstance(value, dict) else {}
        except (LookupError, UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def fetch_json(url: str, *, timeout: int = 20, attempts: int = 2) -> dict[str, Any]:
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    last_error: Exception | None = None
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "application/json,text/plain,*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                result = _decode_json(
                    response.read(8_000_000),
                    response.headers.get_content_charset(),
                )
                if result:
                    return result
                raise RuntimeError("SEC returned an empty or non-JSON response")
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"SEC request failed for {url}: {last_error}")


def parse_ticker_index(payload: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in payload.values():
        if not isinstance(raw, dict):
            continue
        ticker = clean(raw.get("ticker"), 30).upper()
        try:
            cik = f"{int(raw.get('cik_str')):010d}"
        except (TypeError, ValueError):
            continue
        if ticker:
            result[ticker] = cik
    return result


def _column(values: dict[str, Any], key: str) -> list[Any]:
    value = values.get(key, [])
    return value if isinstance(value, list) else []


def _archive_url(cik: str, accession: str, primary_document: str) -> str:
    accession_compact = re.sub(r"\D", "", accession)
    try:
        cik_compact = str(int(cik))
    except (TypeError, ValueError):
        return ""
    document = quote(primary_document.strip(), safe="._-/")
    if not accession_compact or not document:
        return ""
    return f"{ARCHIVES_ROOT}/{cik_compact}/{accession_compact}/{document}"


def parse_submissions(
    payload: dict[str, Any],
    listing: USListing,
    cik: str,
    *,
    max_age_days: int,
    limit: int,
) -> list[dict[str, Any]]:
    filings = payload.get("filings", {})
    recent = filings.get("recent", {}) if isinstance(filings, dict) else {}
    if not isinstance(recent, dict):
        return []
    forms = _column(recent, "form")
    accessions = _column(recent, "accessionNumber")
    filing_dates = _column(recent, "filingDate")
    report_dates = _column(recent, "reportDate")
    primary_documents = _column(recent, "primaryDocument")
    descriptions = _column(recent, "primaryDocDescription")
    count = max(
        len(forms),
        len(accessions),
        len(filing_dates),
        len(primary_documents),
    )
    cutoff = date.today() - timedelta(days=max_age_days)
    accepted: dict[str, dict[str, Any]] = {}
    for index in range(count):
        form = clean(forms[index] if index < len(forms) else "", 30).upper()
        document_type = FORM_TYPES.get(form)
        if not document_type:
            continue
        filed = base.normalize_date(
            str(filing_dates[index] if index < len(filing_dates) else "")
        )
        if not filed:
            continue
        try:
            if date.fromisoformat(filed) < cutoff:
                continue
        except ValueError:
            continue
        accession = clean(accessions[index] if index < len(accessions) else "", 60)
        primary_document = clean(
            primary_documents[index] if index < len(primary_documents) else "",
            300,
        )
        url = _archive_url(cik, accession, primary_document)
        if not url:
            continue
        report_date = base.normalize_date(
            str(report_dates[index] if index < len(report_dates) else "")
        )
        description = clean(
            descriptions[index] if index < len(descriptions) else "",
            300,
        )
        label = FORM_LABELS[document_type]
        title = f"{listing.name} SEC Form {form} — {description or label}"
        summary_parts = [
            f"Ticker {listing.ticker}",
            f"Form {form}",
            label,
            f"Filed {filed}",
            f"Report period {report_date}" if report_date else "",
            f"Accession {accession}" if accession else "",
        ]
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:18]
        event = {
            "id": f"disclosure-{listing.catalog_slug}-{digest}",
            "companySlug": listing.catalog_slug,
            "companyName": listing.name,
            "market": "美股",
            "ticker": listing.ticker,
            "exchange": "美国证券交易委员会 SEC",
            "listingRole": listing.listing_role,
            "publishedAt": filed,
            "documentType": document_type,
            "title": title,
            "summary": " · ".join(part for part in summary_parts if part),
            "source": {
                "name": "美国证券交易委员会 SEC",
                "url": url,
                "level": "监管文件",
            },
            "discoveredVia": PROVIDER,
            "fallback": False,
            "form": form,
            "accessionNumber": accession,
            "reportDate": report_date,
            "cik": cik,
        }
        accepted[url] = event
    return sorted(
        accepted.values(),
        key=lambda event: (event["publishedAt"], event["id"]),
        reverse=True,
    )[: max(1, limit)]


def _event_url(event: dict[str, Any]) -> str:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    return clean(source.get("url"), 1200)


def _merge_events(
    existing: Iterable[dict[str, Any]],
    incoming: Iterable[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for event in [*existing, *incoming]:
        if not isinstance(event, dict):
            continue
        url = _event_url(event)
        if url:
            by_url[url] = event
    return sorted(
        by_url.values(),
        key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
        reverse=True,
    )[: max(1, limit)]


def enrich_snapshot(
    snapshot: dict[str, Any],
    listings: Iterable[USListing],
    ticker_ciks: dict[str, str],
    settings: dict[str, Any],
    *,
    submissions_fetcher=fetch_json,
) -> dict[str, Any]:
    rows = list(listings)
    result = json.loads(json.dumps(snapshot, ensure_ascii=False))
    companies = result.setdefault("companies", {})
    statuses = [
        status for status in result.get("sourceStatus", []) if isinstance(status, dict)
    ]
    us_ids = {listing.source_id for listing in rows}
    statuses = [status for status in statuses if str(status.get("id", "")) not in us_ids]
    max_age_days = max(365, int(settings.get("maxAgeDays", 1095)))
    per_listing_limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    company_limit = max(1, min(per_listing_limit * 2, 60))
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()

    for listing in rows:
        cik = ticker_ciks.get(listing.ticker.upper(), "")
        errors: list[str] = []
        incoming: list[dict[str, Any]] = []
        scanned = 0
        if cik:
            try:
                payload = submissions_fetcher(
                    f"{SUBMISSIONS_ROOT}CIK{cik}.json",
                    timeout=int(settings.get("requestTimeout", 18)),
                    attempts=int(settings.get("requestAttempts", 2)),
                )
                recent = (
                    payload.get("filings", {}).get("recent", {})
                    if isinstance(payload, dict)
                    else {}
                )
                forms = recent.get("form", []) if isinstance(recent, dict) else []
                scanned = len(forms) if isinstance(forms, list) else 0
                incoming = parse_submissions(
                    payload,
                    listing,
                    cik,
                    max_age_days=max_age_days,
                    limit=per_listing_limit,
                )
            except Exception as exc:  # noqa: BLE001 - retain previous verified events.
                errors.append(f"{type(exc).__name__}:{exc}")
        else:
            errors.append("SEC CIK not found for ticker")

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
            continue
        listing_marker = {
            "market": "美股",
            "ticker": listing.ticker,
            "exchange": "美国证券交易委员会 SEC",
            "listingRole": listing.listing_role,
        }
        listing_rows = company.setdefault("listings", [])
        if isinstance(listing_rows, list) and listing_marker not in listing_rows:
            listing_rows.append(listing_marker)
        existing = [
            event for event in company.get("events", []) if isinstance(event, dict)
        ]
        merged = _merge_events(existing, incoming, company_limit)
        company["events"] = merged
        company["updatedAt"] = generated_at
        company["status"] = "ok" if incoming else ("retained" if merged else "partial")
        company["officialEventCount"] = sum(
            not bool(event.get("fallback")) for event in merged
        )
        company["fallbackEventCount"] = sum(
            bool(event.get("fallback")) for event in merged
        )
        statuses.append(
            {
                "id": listing.source_id,
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": "美股",
                "ticker": listing.ticker,
                "exchange": "美国证券交易委员会 SEC",
                "provider": PROVIDER,
                "status": "ok" if incoming else ("retained" if merged else "error"),
                "attempted": True,
                "cikResolved": bool(cik),
                "cik": cik,
                "scanned": scanned,
                "accepted": len(incoming),
                "retainedPrevious": not incoming and bool(merged),
                "errors": errors,
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
    result["secStructured"] = {
        "schemaVersion": 1,
        "provider": PROVIDER,
        "attemptedListingCount": len(rows),
        "acceptedEventCount": sum(
            int(status.get("accepted", 0) or 0)
            for status in statuses
            if str(status.get("id", "")).startswith("sec-disclosure-")
        ),
    }
    return result


def is_sec_archive_url(url: str) -> bool:
    parts = urlsplit(str(url or ""))
    host = (parts.hostname or "").casefold().removeprefix("www.")
    return (
        (host == "sec.gov" or host.endswith(".sec.gov"))
        and "/archives/edgar/data/" in parts.path.casefold()
    )


def _base_only_snapshot(
    snapshot: dict[str, Any],
    exchange_listings: Iterable[base.Listing],
) -> dict[str, Any]:
    rows = list(exchange_listings)
    allowed_slugs = {listing.catalog_slug for listing in rows}
    filtered = json.loads(json.dumps(snapshot, ensure_ascii=False))
    companies: dict[str, Any] = {}
    for slug, company in filtered.get("companies", {}).items():
        if slug not in allowed_slugs or not isinstance(company, dict):
            continue
        next_company = dict(company)
        next_company["events"] = [
            event
            for event in company.get("events", [])
            if isinstance(event, dict) and event.get("market") in {"A股", "港股"}
        ]
        next_company["listings"] = [
            listing
            for listing in company.get("listings", [])
            if isinstance(listing, dict) and listing.get("market") in {"A股", "港股"}
        ]
        next_company["officialEventCount"] = sum(
            not bool(event.get("fallback")) for event in next_company["events"]
        )
        next_company["fallbackEventCount"] = sum(
            bool(event.get("fallback")) for event in next_company["events"]
        )
        companies[slug] = next_company
    filtered["companies"] = companies
    filtered["sourceStatus"] = [
        status
        for status in filtered.get("sourceStatus", [])
        if isinstance(status, dict)
        and not str(status.get("id", "")).startswith("sec-disclosure-")
    ]
    filtered["companyCount"] = len(companies)
    filtered["eventCount"] = sum(
        len(company.get("events", [])) for company in companies.values()
    )
    return filtered


def validate_enrichment(
    snapshot: dict[str, Any],
    listings: Iterable[USListing] | None = None,
    *,
    exchange_listings: Iterable[base.Listing] | None = None,
    require_events: bool = False,
) -> list[str]:
    rows = list(listings or load_us_listings())
    exchange_rows = list(exchange_listings or base.load_listings())
    errors = base.validate_snapshot(
        _base_only_snapshot(snapshot, exchange_rows),
        exchange_rows,
    )
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    companies = snapshot.get("companies", {})
    if not isinstance(companies, dict):
        return [*errors, "companies must be an object"]

    expected_slugs = {listing.catalog_slug for listing in [*exchange_rows, *rows]}
    missing_profiles = sorted(expected_slugs - set(companies))
    if missing_profiles:
        errors.append("missing listed-company profiles: " + ", ".join(missing_profiles))

    for listing in rows:
        status = statuses.get(listing.source_id)
        if not status:
            errors.append(f"missing SEC disclosure status: {listing.source_id}")
            continue
        if status.get("attempted") is not True:
            errors.append(f"SEC source not attempted: {listing.source_id}")
        if status.get("cikResolved") is not True:
            errors.append(f"SEC CIK unresolved: {listing.source_id}")
        company = companies.get(listing.catalog_slug)
        if not isinstance(company, dict):
            errors.append(f"missing SEC company disclosure profile: {listing.catalog_slug}")
            continue
        listing_markers = [
            marker
            for marker in company.get("listings", [])
            if isinstance(marker, dict)
        ]
        if not any(
            marker.get("market") == "美股"
            and str(marker.get("ticker", "")).upper() == listing.ticker
            for marker in listing_markers
        ):
            errors.append(f"missing SEC listing marker: {listing.source_id}")
        events = [
            event
            for event in company.get("events", [])
            if isinstance(event, dict) and event.get("market") == "美股"
        ]
        if require_events and not events:
            errors.append(f"no SEC filings retained: {listing.source_id}")
        for event in events:
            url = _event_url(event)
            if not is_sec_archive_url(url):
                errors.append(f"SEC filing URL outside EDGAR archive: {url}")
            source = event.get("source") if isinstance(event.get("source"), dict) else {}
            if source.get("name") != "美国证券交易委员会 SEC":
                errors.append(f"invalid SEC source label: {event.get('id', 'unknown')}")
            if event.get("documentType") not in ALLOWED_SEC_DOCUMENT_TYPES:
                errors.append(f"invalid SEC document type: {event.get('id', 'unknown')}")
            if not base.normalize_date(str(event.get("publishedAt", ""))):
                errors.append(f"invalid SEC filing date: {event.get('id', 'unknown')}")

    metadata = snapshot.get("secStructured", {})
    if not isinstance(metadata, dict):
        errors.append("secStructured metadata missing")
    else:
        if int(metadata.get("attemptedListingCount", -1)) != len(rows):
            errors.append("secStructured attempted listing count mismatch")
        if require_events and int(metadata.get("acceptedEventCount", 0)) <= 0:
            errors.append("SEC structured query produced no filing events")

    cninfo = snapshot.get("cninfoStructured", {})
    if exchange_rows and any(row.market == "A股" for row in exchange_rows):
        if not isinstance(cninfo, dict) or int(cninfo.get("acceptedEventCount", 0)) <= 0:
            errors.append("CNINFO structured A-share coverage missing from final snapshot")

    if int(snapshot.get("companyCount", -1)) != len(companies):
        errors.append("companyCount does not match listed-company profiles")
    expected_event_count = sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    if int(snapshot.get("eventCount", -1)) != expected_event_count:
        errors.append("eventCount does not match all listed-company events")
    return errors


def write_snapshot(snapshot: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = base.load_previous(path)
    comparable_previous = json.loads(json.dumps(previous, ensure_ascii=False))
    comparable_next = json.loads(json.dumps(snapshot, ensure_ascii=False))
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    for payload in (comparable_previous, comparable_next):
        companies = payload.get("companies", {})
        if isinstance(companies, dict):
            for company in companies.values():
                if isinstance(company, dict):
                    company.pop("updatedAt", None)
    if comparable_previous == comparable_next and path.exists():
        print("No SEC disclosure changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "companyCount": snapshot.get("companyCount", 0),
                "eventCount": snapshot.get("eventCount", 0),
                "secAccepted": snapshot.get("secStructured", {}).get(
                    "acceptedEventCount", 0
                ),
            },
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    args = parser.parse_args()
    listings = load_us_listings()
    if args.check:
        snapshot = base.load_previous(OUTPUT_PATH)
        errors = validate_enrichment(
            snapshot,
            listings,
            require_events=args.require_events,
        )
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
    ticker_index = parse_ticker_index(
        fetch_json(
            TICKER_INDEX_URL,
            timeout=int(settings.get("requestTimeout", 18)),
            attempts=int(settings.get("requestAttempts", 2)),
        )
    )
    snapshot = base.load_previous(OUTPUT_PATH)
    enriched = enrich_snapshot(snapshot, listings, ticker_index, settings)
    errors = validate_enrichment(
        enriched,
        listings,
        require_events=args.require_events,
    )
    if errors:
        raise SystemExit("; ".join(errors))
    write_snapshot(enriched, OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
