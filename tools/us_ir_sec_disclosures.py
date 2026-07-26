#!/usr/bin/env python3
"""Publish US listed-company filings from official investor-relations mirrors.

SEC blocks shared GitHub Actions addresses across its public endpoints. Each
tracked US issuer nevertheless publishes an official SEC Filings table on its
own investor-relations domain. This crawler reads those company-maintained
mirrors, keeps only material filing forms, and merges them into the same formal
listed-company disclosure snapshot used for A-share and Hong Kong companies.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

try:
    from . import crawl_listed_company_disclosures as base
    from . import sec_structured_disclosures as sec
except ImportError:
    import crawl_listed_company_disclosures as base
    import sec_structured_disclosures as sec

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
PROVIDER = "official-company-ir-sec-filings"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0 Safari/537.36"
)
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec"
MONTH_PATTERN = rf"(?:{MONTHS.replace(' ', '|')})"
DATE_PATTERNS = (
    re.compile(rf"\b({MONTH_PATTERN})\s+(\d{{1,2}}),\s+(20\d{{2}})\b", re.I),
    re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2}|\d{2})\b"),
    re.compile(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})\b"),
)
FORM_ALIASES = {
    "SCHEDULE 13D/A": "SC 13D/A",
    "SCHEDULE 13D": "SC 13D",
    "SCHEDULE 13G/A": "SC 13G/A",
    "SCHEDULE 13G": "SC 13G",
    **{form: form for form in sec.FORM_TYPES},
}
FORM_PATTERN = re.compile(
    r"(?<![A-Z0-9])(" + "|".join(
        re.escape(value) for value in sorted(FORM_ALIASES, key=len, reverse=True)
    ) + r")(?![A-Z0-9])",
    re.I,
)


@dataclass(frozen=True)
class IRSource:
    catalog_slug: str
    name: str
    url: str
    host: str
    layout: str


def normalized_host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def load_ir_sources(
    listings: Iterable[sec.USListing] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, IRSource]:
    rows = list(listings or sec.load_us_listings())
    config = config or base.load_config()
    registry = config.get("usInvestorRelations", {})
    registry = registry if isinstance(registry, dict) else {}
    result: dict[str, IRSource] = {}
    for listing in rows:
        raw = registry.get(listing.catalog_slug)
        if not isinstance(raw, dict):
            raise ValueError(f"US investor-relations source missing: {listing.catalog_slug}")
        source = IRSource(
            catalog_slug=listing.catalog_slug,
            name=base.clean_text(raw.get("name"), 160),
            url=base.clean_text(raw.get("url"), 1200),
            host=base.clean_text(raw.get("host"), 200).casefold().removeprefix("www."),
            layout=base.clean_text(raw.get("layout"), 40) or "q4",
        )
        if not all((source.name, source.url, source.host)):
            raise ValueError(f"incomplete US investor-relations source: {listing.catalog_slug}")
        if normalized_host(source.url) != source.host:
            raise ValueError(f"US IR source host mismatch: {listing.catalog_slug}")
        result[listing.catalog_slug] = source
    return result


def fetch_text(url: str, *, timeout: int = 18, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.6",
                "Accept-Encoding": "identity",
                "Connection": "close",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(5_000_000).decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"US IR request failed for {url}: {last_error}")


def page_url(source: IRSource, page: int) -> str:
    parts = urlsplit(source.url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["page"] = str(max(0, page))
    if source.layout == "q4":
        query["items_per_page"] = "100"
        query["items_per_page_toggle"] = "0"
        query["mobile"] = "1"
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))


def normalize_form(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", str(value or "").upper()).strip()
    return FORM_ALIASES.get(cleaned, cleaned)


def extract_form(text: str) -> str:
    match = FORM_PATTERN.search(re.sub(r"\s+", " ", str(text or "").upper()))
    return normalize_form(match.group(1)) if match else ""


def extract_date(text: str) -> str:
    value = str(text or "")
    month_match = DATE_PATTERNS[0].search(value)
    if month_match:
        try:
            return datetime.strptime(
                " ".join(month_match.groups()), "%b %d %Y"
            ).date().isoformat()
        except ValueError:
            pass
    slash_match = DATE_PATTERNS[1].search(value)
    if slash_match:
        month, day, year = slash_match.groups()
        if len(year) == 2:
            year = "20" + year
        try:
            return date(int(year), int(month), int(day)).isoformat()
        except ValueError:
            pass
    iso_match = DATE_PATTERNS[2].search(value)
    if iso_match:
        try:
            return date(*(int(value) for value in iso_match.groups())).isoformat()
        except ValueError:
            pass
    return ""


def _same_or_sec_host(source: IRSource, url: str) -> bool:
    host = normalized_host(url)
    return host == source.host or host == "sec.gov" or host.endswith(".sec.gov")


def _preferred_link(
    source: IRSource,
    links: list[tuple[str, str]],
) -> str:
    valid = [url for url, _anchor in links if _same_or_sec_host(source, url)]
    if not valid:
        return ""
    priorities = (
        "/sec-filings/sec-filing/",
        "/sec-filings/all-sec-filings/content/",
        "/node/",
        "/content/",
        "/archives/edgar/data/",
    )
    for marker in priorities:
        for url in valid:
            if marker in urlsplit(url).path.casefold():
                return url
    html_links = [
        url
        for url in valid
        if urlsplit(url).path.casefold().endswith((".htm", ".html"))
    ]
    return html_links[0] if html_links else valid[0]


def _description(row_text: str, form: str, published_at: str) -> str:
    text = base.clean_text(row_text, 1600)
    for pattern in DATE_PATTERNS:
        text = pattern.sub(" ", text, count=1)
    if form:
        text = re.sub(re.escape(form), " ", text, count=1, flags=re.I)
        for alias, normalized in FORM_ALIASES.items():
            if normalized == form:
                text = re.sub(re.escape(alias), " ", text, count=1, flags=re.I)
    text = re.sub(
        r"\b(Filing Date|Filing date|Date|Form|Description|Filing Group|View|PDF|HTML|XBRL|Pages)\b",
        " ",
        text,
        flags=re.I,
    )
    text = re.sub(r"\b\d{10}-\d{2}-\d{6}\.(?:pdf|rtf|xls)\b", " ", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip(" |_-—")
    return text[:500] or f"Official investor-relations mirror of SEC Form {form} filed {published_at}."


def parse_page(
    body: str,
    source: IRSource,
    listing: sec.USListing,
) -> tuple[list[dict[str, Any]], int]:
    parser = base.TableRowParser(source.url)
    parser.feed(body)
    rows = parser.rows
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row_text, links in rows:
        form = extract_form(row_text)
        document_type = sec.FORM_TYPES.get(form)
        if not document_type:
            continue
        published_at = extract_date(row_text)
        if not published_at:
            continue
        url = _preferred_link(source, links)
        if not url or url in seen:
            continue
        description = _description(row_text, form, published_at)
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:18]
        events.append(
            {
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
                "summary": (
                    f"Ticker {listing.ticker} · Form {form} · Filed {published_at} · "
                    f"Official filing mirror maintained by {source.name}."
                ),
                "source": {
                    "name": source.name,
                    "url": url,
                    "level": "监管文件",
                },
                "discoveredVia": PROVIDER,
                "fallback": False,
                "regulatoryMirror": True,
                "form": form,
            }
        )
        seen.add(url)
    return events, len(rows)


def crawl_source(
    listing: sec.USListing,
    source: IRSource,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    timeout = int(settings.get("requestTimeout", 18))
    attempts = int(settings.get("requestAttempts", 2))
    limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    max_pages = max(1, min(int(settings.get("usIrMaxPages", 12)), 20))
    cutoff = date.today() - timedelta(days=int(settings.get("maxAgeDays", 1095)))
    accepted: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    scanned = 0
    empty_pages = 0
    for page in range(max_pages):
        url = page_url(source, page)
        try:
            body = fetch_text(url, timeout=timeout, attempts=attempts)
            events, page_scanned = parse_page(body, source, listing)
        except Exception as exc:  # noqa: BLE001 - retain previous verified batch.
            errors.append(f"page-{page}:{type(exc).__name__}:{exc}")
            if page == 0:
                break
            continue
        scanned += page_scanned
        if not events:
            empty_pages += 1
        else:
            empty_pages = 0
        for event in events:
            try:
                if date.fromisoformat(event["publishedAt"]) < cutoff:
                    continue
            except ValueError:
                continue
            accepted[event["source"]["url"]] = event
        if len(accepted) >= limit:
            break
        if page > 0 and empty_pages >= 2:
            break
        time.sleep(0.35)
    rows = sorted(
        accepted.values(),
        key=lambda event: (event["publishedAt"], event["id"]),
        reverse=True,
    )[:limit]
    return rows, {
        "id": f"us-ir-disclosure-{listing.catalog_slug}-{listing.ticker.casefold()}",
        "companySlug": listing.catalog_slug,
        "name": listing.name,
        "market": "美股",
        "ticker": listing.ticker,
        "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
        "provider": PROVIDER,
        "sourceName": source.name,
        "sourceUrl": source.url,
        "sourceHost": source.host,
        "status": "ok" if rows else "error",
        "attempted": True,
        "scanned": scanned,
        "accepted": len(rows),
        "errors": errors,
    }


def _event_url(event: dict[str, Any]) -> str:
    source = event.get("source") if isinstance(event.get("source"), dict) else {}
    return base.clean_text(source.get("url"), 1200)


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


def build_snapshot(
    previous: dict[str, Any] | None = None,
    listings: Iterable[sec.USListing] | None = None,
) -> dict[str, Any]:
    config = base.load_config()
    settings = config["settings"]
    rows = list(listings or sec.load_us_listings())
    sources = load_ir_sources(rows, config)
    previous = previous or base.load_previous(OUTPUT_PATH)
    result = json.loads(json.dumps(previous, ensure_ascii=False))
    companies = result.setdefault("companies", {})
    statuses = [
        status
        for status in result.get("sourceStatus", [])
        if isinstance(status, dict)
        and not str(status.get("id", "")).startswith("us-ir-disclosure-")
        and not str(status.get("id", "")).startswith("sec-disclosure-")
    ]
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    per_listing_limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    company_limit = max(1, min(per_listing_limit * 2, 60))

    for listing in rows:
        source = sources[listing.catalog_slug]
        try:
            events, status = crawl_source(listing, source, settings)
        except Exception as exc:  # noqa: BLE001
            events = []
            status = {
                "id": f"us-ir-disclosure-{listing.catalog_slug}-{listing.ticker.casefold()}",
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": "美股",
                "ticker": listing.ticker,
                "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
                "provider": PROVIDER,
                "sourceName": source.name,
                "sourceUrl": source.url,
                "sourceHost": source.host,
                "status": "error",
                "attempted": True,
                "scanned": 0,
                "accepted": 0,
                "errors": [f"{type(exc).__name__}:{exc}"],
            }
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
        marker = {
            "market": "美股",
            "ticker": listing.ticker,
            "exchange": "美国证券交易委员会 SEC（公司 IR 镜像）",
            "listingRole": listing.listing_role,
        }
        listing_rows = company.setdefault("listings", [])
        if isinstance(listing_rows, list) and marker not in listing_rows:
            listing_rows.append(marker)
        existing = [
            event for event in company.get("events", []) if isinstance(event, dict)
        ]
        merged = _merge_events(existing, events, company_limit)
        company["events"] = merged
        company["updatedAt"] = generated_at
        company["status"] = "ok" if events else ("retained" if merged else "partial")
        company["officialEventCount"] = sum(
            not bool(event.get("fallback")) for event in merged
        )
        company["fallbackEventCount"] = sum(
            bool(event.get("fallback")) for event in merged
        )
        if not events and merged:
            status["status"] = "retained"
            status["retainedPrevious"] = True
        statuses.append(status)

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
        "provider": PROVIDER,
        "attemptedListingCount": len(rows),
        "acceptedEventCount": sum(
            int(status.get("accepted", 0) or 0)
            for status in statuses
            if str(status.get("id", "")).startswith("us-ir-disclosure-")
        ),
        "directSecAccess": "blocked-by-sec-for-shared-ci-ip",
    }
    return result


def _exchange_only_snapshot(
    snapshot: dict[str, Any],
    exchange_rows: Iterable[base.Listing],
) -> dict[str, Any]:
    rows = list(exchange_rows)
    slugs = {row.catalog_slug for row in rows}
    filtered = json.loads(json.dumps(snapshot, ensure_ascii=False))
    companies: dict[str, Any] = {}
    for slug, company in filtered.get("companies", {}).items():
        if slug not in slugs or not isinstance(company, dict):
            continue
        next_company = dict(company)
        next_company["events"] = [
            event
            for event in company.get("events", [])
            if isinstance(event, dict) and event.get("market") in {"A股", "港股"}
        ]
        next_company["listings"] = [
            marker
            for marker in company.get("listings", [])
            if isinstance(marker, dict) and marker.get("market") in {"A股", "港股"}
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
        and not str(status.get("id", "")).startswith("us-ir-disclosure-")
        and not str(status.get("id", "")).startswith("sec-disclosure-")
    ]
    filtered["companyCount"] = len(companies)
    filtered["eventCount"] = sum(
        len(company.get("events", [])) for company in companies.values()
    )
    return filtered


def validate_snapshot(
    snapshot: dict[str, Any],
    listings: Iterable[sec.USListing] | None = None,
    *,
    require_events: bool = False,
) -> list[str]:
    rows = list(listings or sec.load_us_listings())
    exchange_rows = base.load_listings()
    errors = base.validate_snapshot(
        _exchange_only_snapshot(snapshot, exchange_rows),
        exchange_rows,
    )
    sources = load_ir_sources(rows)
    companies = snapshot.get("companies", {})
    if not isinstance(companies, dict):
        return [*errors, "companies must be an object"]
    statuses = {
        str(status.get("id", "")): status
        for status in snapshot.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    expected_slugs = {
        row.catalog_slug for row in [*exchange_rows, *rows]
    }
    missing = sorted(expected_slugs - set(companies))
    if missing:
        errors.append("missing listed-company profiles: " + ", ".join(missing))

    for listing in rows:
        status_id = f"us-ir-disclosure-{listing.catalog_slug}-{listing.ticker.casefold()}"
        status = statuses.get(status_id)
        if not status:
            errors.append(f"missing US IR disclosure status: {status_id}")
            continue
        if status.get("attempted") is not True:
            errors.append(f"US IR source not attempted: {status_id}")
        if require_events and int(status.get("accepted", 0) or 0) <= 0:
            errors.append(f"US IR source accepted no filings: {status_id}")
        company = companies.get(listing.catalog_slug)
        if not isinstance(company, dict):
            continue
        events = [
            event
            for event in company.get("events", [])
            if isinstance(event, dict) and event.get("market") == "美股"
        ]
        if require_events and not events:
            errors.append(f"no US filing events retained: {status_id}")
        source = sources[listing.catalog_slug]
        for event in events:
            url = _event_url(event)
            host = normalized_host(url)
            if host != source.host and not (host == "sec.gov" or host.endswith(".sec.gov")):
                errors.append(f"US filing URL outside official source: {url}")
            event_source = event.get("source") if isinstance(event.get("source"), dict) else {}
            if event_source.get("name") != source.name:
                errors.append(f"US filing source label mismatch: {event.get('id', 'unknown')}")
            if event.get("documentType") not in sec.ALLOWED_SEC_DOCUMENT_TYPES:
                errors.append(f"invalid US filing type: {event.get('id', 'unknown')}")

    metadata = snapshot.get("usIrStructured", {})
    if not isinstance(metadata, dict):
        errors.append("usIrStructured metadata missing")
    else:
        if int(metadata.get("attemptedListingCount", -1)) != len(rows):
            errors.append("US IR attempted listing count mismatch")
        if require_events and int(metadata.get("acceptedEventCount", 0)) <= 0:
            errors.append("US IR sources produced no filing events")
    if int(snapshot.get("companyCount", -1)) != len(companies):
        errors.append("companyCount does not match company profiles")
    expected_events = sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    if int(snapshot.get("eventCount", -1)) != expected_events:
        errors.append("eventCount does not match disclosure events")
    return errors


def write_snapshot(snapshot: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    return sec.write_snapshot(snapshot, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-events", action="store_true")
    args = parser.parse_args()
    listings = sec.load_us_listings()
    if args.check:
        snapshot = base.load_previous(OUTPUT_PATH)
        errors = validate_snapshot(snapshot, listings, require_events=args.require_events)
        if errors:
            raise SystemExit("; ".join(errors))
        print(
            json.dumps(
                {
                    "passed": True,
                    "listedCompanyCount": len(listings),
                    "acceptedEventCount": snapshot.get("usIrStructured", {}).get(
                        "acceptedEventCount", 0
                    ),
                },
                ensure_ascii=False,
            )
        )
        return 0
    snapshot = build_snapshot(base.load_previous(OUTPUT_PATH), listings)
    errors = validate_snapshot(snapshot, listings, require_events=args.require_events)
    if errors:
        status_errors = [
            status
            for status in snapshot.get("sourceStatus", [])
            if str(status.get("id", "")).startswith("us-ir-disclosure-")
        ]
        print(json.dumps({"statuses": status_errors}, ensure_ascii=False))
        raise SystemExit("; ".join(errors))
    write_snapshot(snapshot, OUTPUT_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
