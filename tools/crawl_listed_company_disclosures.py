#!/usr/bin/env python3
"""Build a structured listed-company disclosure snapshot.

The crawler covers enabled A-share and Hong Kong listings from
``config/user_tracking.json``. It prioritizes official disclosure hosts:

* Shanghai Stock Exchange and CNINFO for Shanghai listings;
* Shenzhen Stock Exchange and CNINFO for Shenzhen listings;
* HKEXnews for Hong Kong listings.

Domain-restricted public search is used only for URL discovery. Every published
record must resolve to an allowlisted original disclosure host. Eastmoney's
announcement database is used only when a listing yields no official result.
The crawler stores document metadata and short factual snippets, never full PDF
or announcement text.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
CONFIG_PATH = ROOT / "config" / "listed_company_disclosure_sources.json"
OUTPUT_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
USER_AGENT = (
    "No1LizeResearchBot/1.0 contact=No1Lize@users.noreply.github.com "
    "(+https://github.com/No1Lize/No1Lize.github.io)"
)
SUPPORTED_MARKETS = {"A股", "港股"}
CAPITAL_TERMS_ZH = (
    "招股说明书",
    "招股章程",
    "上市公告",
    "年度报告",
    "半年度报告",
    "季度报告",
    "业绩预告",
    "业绩快报",
    "配售",
    "定向增发",
    "非公开发行",
    "发行股份",
    "可转换债券",
    "公司债券",
    "募集资金",
    "重大资产重组",
    "收购",
    "并购",
    "出售资产",
    "股权激励",
    "股份回购",
    "回购股份",
    "重大合同",
    "重大事项",
    "关联交易",
)
CAPITAL_TERMS_EN = (
    "prospectus",
    "listing document",
    "global offering",
    "annual report",
    "interim report",
    "quarterly results",
    "profit warning",
    "placing",
    "issue of shares",
    "issue of securities",
    "convertible bond",
    "notes issue",
    "acquisition",
    "disposal",
    "major transaction",
    "share scheme",
    "share option",
    "restricted share units",
    "repurchase",
    "business update",
    "inside information",
)
ROUTINE_NOISE = (
    "monthly return",
    "next day disclosure return",
    "notice of board meeting",
    "poll results",
    "list of directors",
    "terms of reference",
    "月报表",
    "董事名单",
    "股东大会通知",
    "股东大会决议",
)


@dataclass(frozen=True)
class Listing:
    catalog_slug: str
    name: str
    market: str
    ticker: str
    sector: str
    listing_role: str = "primary"

    @property
    def identity(self) -> str:
        return f"{self.catalog_slug}:{self.market}:{self.ticker}"

    @property
    def source_id(self) -> str:
        digest = re.sub(r"[^a-z0-9]+", "-", self.catalog_slug.casefold()).strip("-")
        market = "a" if self.market == "A股" else "hk"
        return f"exchange-disclosure-{digest}-{market}-{self.ticker.casefold()}"

    @property
    def exchange(self) -> str:
        if self.market == "港股":
            return "香港交易所"
        return "上海证券交易所" if a_share_exchange(self.ticker) == "sse" else "深圳证券交易所"


@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    summary: str
    published_at: str
    provider: str


def clean_text(value: Any, limit: int = 1000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" |_-—")
    return text[:limit]


def normalized_host(url: str) -> str:
    return (urlsplit(str(url or "")).hostname or "").casefold().removeprefix("www.")


def a_share_exchange(ticker: str) -> str:
    return "sse" if str(ticker).startswith(("5", "6", "9")) else "szse"


def normalize_ticker(market: str, value: Any) -> str:
    raw = re.sub(r"\s+", "", str(value or "")).upper()
    if market == "A股":
        digits = re.sub(r"\D", "", raw)
        return digits if re.fullmatch(r"\d{6}", digits) else ""
    if market == "港股":
        digits = re.sub(r"\D", "", raw)
        return digits.zfill(5) if 1 <= len(digits) <= 5 else ""
    return ""


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported listed disclosure config schema")
    if not isinstance(payload.get("settings"), dict):
        raise ValueError("listed disclosure config requires settings")
    return payload


def load_listings(
    tracking_path: Path = TRACKING_PATH,
    config_path: Path = CONFIG_PATH,
) -> list[Listing]:
    tracking = json.loads(tracking_path.read_text(encoding="utf-8"))
    config = load_config(config_path)
    raw_rows = [
        row
        for row in tracking.get("listedCompanies", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market") in SUPPORTED_MARKETS
    ]
    raw_rows.extend(
        row
        for row in config.get("extraListings", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market") in SUPPORTED_MARKETS
    )
    listings: list[Listing] = []
    seen: set[str] = set()
    for row in raw_rows:
        market = clean_text(row.get("market"), 20)
        ticker = normalize_ticker(market, row.get("ticker"))
        listing = Listing(
            catalog_slug=clean_text(row.get("catalogSlug"), 80),
            name=clean_text(row.get("name"), 120),
            market=market,
            ticker=ticker,
            sector=clean_text(row.get("sector"), 60),
            listing_role=clean_text(row.get("listingRole", "primary"), 20) or "primary",
        )
        if not all((listing.catalog_slug, listing.name, listing.ticker, listing.sector)):
            raise ValueError(f"incomplete listed-company disclosure row: {row}")
        if listing.identity in seen:
            continue
        seen.add(listing.identity)
        listings.append(listing)
    return listings


def bing_rss(query: str) -> str:
    return "https://www.bing.com/news/search?q=" + quote_plus(query) + "&format=rss"


def official_query(listing: Listing) -> str:
    terms = " OR ".join(f'"{term}"' for term in (*CAPITAL_TERMS_ZH, *CAPITAL_TERMS_EN))
    identity = f'("{listing.ticker}" OR "{listing.name}")'
    if listing.market == "港股":
        sites = "site:hkexnews.hk/listedco/listconews/sehk"
    elif a_share_exchange(listing.ticker) == "sse":
        sites = "(site:cninfo.com.cn OR site:sse.com.cn/disclosure)"
    else:
        sites = "(site:cninfo.com.cn OR site:szse.cn/disclosure)"
    return f"{sites} {identity} ({terms})"


def fallback_query(listing: Listing) -> str:
    terms = " OR ".join(f'"{term}"' for term in CAPITAL_TERMS_ZH[:18])
    return (
        "site:data.eastmoney.com/notices "
        f'("{listing.ticker}" OR "{listing.name}") ({terms})'
    )


def fetch_text(url: str, timeout: int, attempts: int) -> str:
    last_error: Exception | None = None
    for attempt in range(max(1, min(attempts, 3))):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/rss+xml,application/xml,text/xml,text/html;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return response.read(3_000_000).decode(charset, errors="replace")
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.1 * (attempt + 1))
    raise RuntimeError(f"fetch failed for {url}: {last_error}")


def normalize_date(value: str) -> str:
    raw = clean_text(value, 100)
    if not raw:
        return ""
    try:
        parsed = parsedate_to_datetime(raw)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", raw)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError:
            return ""
    return ""


def parse_rss(body: str, provider: str) -> list[Candidate]:
    root = ET.fromstring(body)
    rows: list[Candidate] = []
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1].casefold() not in {"item", "entry"}:
            continue
        values: dict[str, str] = {}
        for child in node.iter():
            key = child.tag.rsplit("}", 1)[-1].casefold()
            if key == "link":
                value = clean_text(child.attrib.get("href", ""), 1000) or clean_text(child.text, 1000)
            else:
                value = clean_text(child.text, 2000)
            if value and key not in values:
                values[key] = value
        title = clean_text(values.get("title"), 500)
        url = clean_text(values.get("link"), 1200)
        summary = clean_text(values.get("description") or values.get("summary"), 1000)
        published = normalize_date(
            values.get("pubdate")
            or values.get("published")
            or values.get("updated")
            or summary
        )
        if title and url:
            rows.append(Candidate(title, url, summary, published, provider))
    return rows


def source_name(url: str) -> tuple[str, str]:
    host = normalized_host(url)
    if host == "cninfo.com.cn" or host.endswith(".cninfo.com.cn"):
        return "巨潮资讯", "监管文件"
    if host == "sse.com.cn" or host.endswith(".sse.com.cn"):
        return "上海证券交易所", "监管文件"
    if host == "szse.cn" or host.endswith(".szse.cn"):
        return "深圳证券交易所", "监管文件"
    if host == "hkexnews.hk" or host.endswith(".hkexnews.hk"):
        return "香港交易所披露易", "监管文件"
    if host == "eastmoney.com" or host.endswith(".eastmoney.com"):
        return "东方财富公告", "数据库记录"
    return "", ""


def allowed_url(listing: Listing, url: str, *, fallback: bool = False) -> bool:
    host = normalized_host(url)
    path = urlsplit(url).path.casefold()
    if fallback:
        return (
            (host == "eastmoney.com" or host.endswith(".eastmoney.com"))
            and "/notices" in path
        )
    if listing.market == "港股":
        return (
            (host == "hkexnews.hk" or host.endswith(".hkexnews.hk"))
            and ("/listedco/" in path or "/search/" in path)
        )
    if host == "cninfo.com.cn" or host.endswith(".cninfo.com.cn"):
        return "/disclosure/" in path or "/finalpage/" in path or "/fulltextsearch" in path
    exchange = a_share_exchange(listing.ticker)
    if exchange == "sse":
        return (host == "sse.com.cn" or host.endswith(".sse.com.cn")) and "/disclosure" in path
    return (host == "szse.cn" or host.endswith(".szse.cn")) and "/disclosure" in path


def relevant_candidate(listing: Listing, candidate: Candidate) -> bool:
    text = clean_text(
        f"{candidate.title} {candidate.summary} {candidate.url}",
        5000,
    ).casefold()
    ticker_variants = {listing.ticker.casefold(), listing.ticker.lstrip("0").casefold()}
    name_variants = {
        listing.name.casefold(),
        listing.name.replace("机器人", "").casefold(),
        listing.name.replace("科技", "").casefold(),
    }
    return any(term and term in text for term in (*ticker_variants, *name_variants))


def classify_document(title: str, summary: str = "") -> str:
    text = clean_text(f"{title} {summary}", 3000).casefold()
    if any(term in text for term in ROUTINE_NOISE):
        return ""
    groups = (
        ("招股与上市", ("招股说明书", "招股章程", "上市公告", "prospectus", "listing document", "global offering")),
        ("定期报告与业绩", ("年度报告", "半年度报告", "季度报告", "业绩预告", "业绩快报", "annual report", "interim report", "quarterly results", "profit warning")),
        ("证券发行与融资", ("配售", "定向增发", "非公开发行", "发行股份", "可转换债券", "公司债券", "募集资金", "placing", "issue of shares", "issue of securities", "convertible bond", "notes issue")),
        ("并购与资产交易", ("重大资产重组", "收购", "并购", "出售资产", "acquisition", "disposal", "major transaction")),
        ("股权激励", ("股权激励", "share scheme", "share option", "restricted share units")),
        ("股份回购", ("股份回购", "回购股份", "repurchase")),
        ("重大经营与风险", ("重大合同", "重大事项", "关联交易", "business update", "inside information")),
    )
    for label, terms in groups:
        if any(term in text for term in terms):
            return label
    return ""


def event_id(listing: Listing, url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:18]
    return f"disclosure-{listing.catalog_slug}-{digest}"


def to_event(listing: Listing, candidate: Candidate, *, fallback: bool) -> dict[str, Any] | None:
    if not candidate.published_at:
        return None
    document_type = classify_document(candidate.title, candidate.summary)
    if not document_type:
        return None
    source, level = source_name(candidate.url)
    if not source:
        return None
    summary = candidate.summary or f"{source}公开披露：{candidate.title}"
    summary = clean_text(summary, 360)
    return {
        "id": event_id(listing, candidate.url),
        "companySlug": listing.catalog_slug,
        "companyName": listing.name,
        "market": listing.market,
        "ticker": listing.ticker,
        "exchange": listing.exchange,
        "listingRole": listing.listing_role,
        "publishedAt": candidate.published_at,
        "documentType": document_type,
        "title": candidate.title,
        "summary": summary,
        "source": {
            "name": source,
            "url": candidate.url,
            "level": level,
        },
        "discoveredVia": candidate.provider,
        "fallback": fallback,
    }


def discover(
    listing: Listing,
    settings: dict[str, Any],
    *,
    fallback: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = fallback_query(listing) if fallback else official_query(listing)
    provider = "eastmoney-domain-search" if fallback else "official-domain-search"
    body = fetch_text(
        bing_rss(query),
        int(settings.get("requestTimeout", 18)),
        int(settings.get("requestAttempts", 2)),
    )
    candidates = parse_rss(body, provider)
    cutoff = date.today() - timedelta(days=int(settings.get("maxAgeDays", 1095)))
    accepted: list[dict[str, Any]] = []
    for candidate in candidates:
        if not allowed_url(listing, candidate.url, fallback=fallback):
            continue
        if not relevant_candidate(listing, candidate):
            continue
        event = to_event(listing, candidate, fallback=fallback)
        if not event:
            continue
        try:
            if date.fromisoformat(event["publishedAt"]) < cutoff:
                continue
        except ValueError:
            continue
        accepted.append(event)
    limit = max(1, min(int(settings.get("maxItemsPerListing", 18)), 30))
    deduplicated = {event["source"]["url"]: event for event in accepted}
    rows = sorted(
        deduplicated.values(),
        key=lambda event: (event["publishedAt"], event["id"]),
        reverse=True,
    )[:limit]
    return rows, {
        "id": listing.source_id,
        "companySlug": listing.catalog_slug,
        "name": listing.name,
        "market": listing.market,
        "ticker": listing.ticker,
        "exchange": listing.exchange,
        "provider": provider,
        "status": "ok" if rows else "error",
        "scanned": len(candidates),
        "accepted": len(rows),
        "fallback": fallback,
    }


def load_previous(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"schemaVersion": 1, "companies": {}, "sourceStatus": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schemaVersion": 1, "companies": {}, "sourceStatus": []}
    return payload if isinstance(payload, dict) else {"schemaVersion": 1, "companies": {}, "sourceStatus": []}


def build_snapshot(
    listings: Iterable[Listing] | None = None,
    previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    config = load_config()
    settings = config["settings"]
    rows = list(listings or load_listings())
    previous = previous or load_previous()
    previous_companies = previous.get("companies", {}) if isinstance(previous.get("companies"), dict) else {}
    events_by_company: dict[str, dict[str, dict[str, Any]]] = {}
    listing_rows_by_company: dict[str, list[dict[str, Any]]] = {}
    statuses: list[dict[str, Any]] = []

    for listing in rows:
        events: list[dict[str, Any]] = []
        try:
            events, status = discover(listing, settings, fallback=False)
        except Exception as exc:  # noqa: BLE001 - retain prior verified disclosure data.
            status = {
                "id": listing.source_id,
                "companySlug": listing.catalog_slug,
                "name": listing.name,
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
                "provider": "official-domain-search",
                "status": "error",
                "scanned": 0,
                "accepted": 0,
                "fallback": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        if not events and bool(settings.get("fallbackEnabled", True)):
            try:
                fallback_events, fallback_status = discover(listing, settings, fallback=True)
                if fallback_events:
                    events = fallback_events
                    status["status"] = "partial"
                    status["fallbackUsed"] = True
                    status["accepted"] = len(events)
                status["fallbackScanned"] = fallback_status.get("scanned", 0)
                status["fallbackAccepted"] = fallback_status.get("accepted", 0)
            except Exception as exc:  # noqa: BLE001 - official error remains diagnostic.
                status["fallbackError"] = f"{type(exc).__name__}: {exc}"

        company_events = events_by_company.setdefault(listing.catalog_slug, {})
        for event in events:
            company_events[event["source"]["url"]] = event
        listing_rows_by_company.setdefault(listing.catalog_slug, []).append(
            {
                "market": listing.market,
                "ticker": listing.ticker,
                "exchange": listing.exchange,
                "listingRole": listing.listing_role,
            }
        )
        statuses.append(status)

    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    companies: dict[str, Any] = {}
    slugs = sorted({listing.catalog_slug for listing in rows})
    for slug in slugs:
        current = list(events_by_company.get(slug, {}).values())
        previous_company = previous_companies.get(slug, {}) if isinstance(previous_companies.get(slug), dict) else {}
        previous_events = [
            event for event in previous_company.get("events", []) if isinstance(event, dict)
        ]
        by_url = {
            str(event.get("source", {}).get("url", "")): event
            for event in previous_events
            if str(event.get("source", {}).get("url", ""))
        }
        for event in current:
            by_url[event["source"]["url"]] = event
        max_company_items = max(1, min(int(settings.get("maxItemsPerListing", 18)) * 2, 48))
        merged = sorted(
            by_url.values(),
            key=lambda event: (str(event.get("publishedAt", "")), str(event.get("id", ""))),
            reverse=True,
        )[:max_company_items]
        listing_info = listing_rows_by_company.get(slug, [])
        name = next((listing.name for listing in rows if listing.catalog_slug == slug), slug)
        new_count = sum(1 for event in current)
        companies[slug] = {
            "slug": slug,
            "name": name,
            "updatedAt": generated_at,
            "status": "ok" if new_count else ("retained" if merged else "partial"),
            "listings": listing_info,
            "events": merged,
            "officialEventCount": sum(not bool(event.get("fallback")) for event in merged),
            "fallbackEventCount": sum(bool(event.get("fallback")) for event in merged),
        }

    return {
        "schemaVersion": 1,
        "generatedAt": generated_at,
        "companyCount": len(companies),
        "eventCount": sum(len(company["events"]) for company in companies.values()),
        "companies": companies,
        "sourceStatus": statuses,
    }


def validate_snapshot(payload: dict[str, Any], listings: Iterable[Listing] | None = None) -> list[str]:
    errors: list[str] = []
    rows = list(listings or load_listings())
    expected_status = {listing.source_id for listing in rows}
    statuses = {
        str(status.get("id")): status
        for status in payload.get("sourceStatus", [])
        if isinstance(status, dict)
    }
    missing = sorted(expected_status - set(statuses))
    if missing:
        errors.append("missing disclosure source statuses: " + ", ".join(missing[:10]))
    companies = payload.get("companies")
    if not isinstance(companies, dict):
        errors.append("companies must be an object")
        return errors
    for listing in rows:
        company = companies.get(listing.catalog_slug)
        if not isinstance(company, dict):
            errors.append(f"missing disclosure company: {listing.catalog_slug}")
            continue
        for event in company.get("events", []):
            if not isinstance(event, dict):
                errors.append(f"invalid event row: {listing.catalog_slug}")
                continue
            source = event.get("source") if isinstance(event.get("source"), dict) else {}
            url = str(source.get("url", ""))
            fallback = bool(event.get("fallback"))
            if not allowed_url(listing, url, fallback=fallback):
                errors.append(f"disclosure URL outside allowlist: {url}")
            if not classify_document(str(event.get("title", "")), str(event.get("summary", ""))):
                errors.append(f"unclassified disclosure event: {event.get('id', 'unknown')}")
            if not normalize_date(str(event.get("publishedAt", ""))):
                errors.append(f"invalid disclosure date: {event.get('id', 'unknown')}")
    if int(payload.get("eventCount", -1)) != sum(
        len(company.get("events", []))
        for company in companies.values()
        if isinstance(company, dict)
    ):
        errors.append("eventCount does not match disclosure events")
    return errors


def write_snapshot(payload: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    previous = load_previous(path)
    comparable_previous = dict(previous)
    comparable_next = dict(payload)
    comparable_previous.pop("generatedAt", None)
    comparable_next.pop("generatedAt", None)
    for company in comparable_previous.get("companies", {}).values() if isinstance(comparable_previous.get("companies"), dict) else []:
        if isinstance(company, dict):
            company.pop("updatedAt", None)
    for company in comparable_next.get("companies", {}).values() if isinstance(comparable_next.get("companies"), dict) else []:
        if isinstance(company, dict):
            company.pop("updatedAt", None)
    if comparable_previous == comparable_next and path.exists():
        print("No listed-company disclosure changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "companies": payload.get("companyCount", 0),
                "events": payload.get("eventCount", 0),
                "officialEvents": sum(
                    int(company.get("officialEventCount", 0) or 0)
                    for company in payload.get("companies", {}).values()
                    if isinstance(company, dict)
                ),
                "fallbackEvents": sum(
                    int(company.get("fallbackEventCount", 0) or 0)
                    for company in payload.get("companies", {}).values()
                    if isinstance(company, dict)
                ),
            },
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if args.validate_only:
        payload = load_previous()
        errors = validate_snapshot(payload)
        if errors:
            raise SystemExit("; ".join(errors))
        print(json.dumps({"passed": True, "eventCount": payload.get("eventCount", 0)}, ensure_ascii=False))
        return 0
    payload = build_snapshot()
    errors = validate_snapshot(payload)
    if errors:
        raise SystemExit("; ".join(errors))
    write_snapshot(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
