#!/usr/bin/env python3
"""Archive public research-related PDFs for every enabled listed company.

The crawler uses multiple public, unauthenticated discovery paths:

* Eastmoney's public research-report endpoint when it returns matching records;
* public web/RSS discovery for broker research, investor presentations, annual
  reports, prospectuses and other company-research PDFs;
* the company website recorded in the market-profile snapshot as a preferred
  domain when available.

Only files that validate as PDFs are archived. The crawler never authenticates,
bypasses paywalls or stores HTML/login pages as PDFs. A failed or empty refresh
retains the most recent validated files for that company.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote_plus, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from tools.research_report_adapters import (
        discover_sec_candidates,
        discover_web_candidates,
        load_sec_ticker_map,
    )
except ModuleNotFoundError:  # direct execution: python tools/crawl_research_reports.py
    from research_report_adapters import (
        discover_sec_candidates,
        discover_web_candidates,
        load_sec_ticker_map,
    )

try:
    from tools.research_report_registry import (
        load_local_cik_map,
        load_official_websites,
        merge_source_maps,
    )
except ModuleNotFoundError:  # direct execution
    from research_report_registry import (
        load_local_cik_map,
        load_official_websites,
        merge_source_maps,
    )

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
MARKET_PROFILE_PATH = ROOT / "public" / "data" / "market_profiles.json"
INDEX_PATH = ROOT / "public" / "data" / "research_reports.json"
PDF_DIR = ROOT / "public" / "research-reports"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
BING_RSS = "https://www.bing.com/search?format=rss&q={query}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
MAX_REPORTS_PER_COMPANY = int(os.getenv("RESEARCH_REPORTS_PER_COMPANY", "3"))
MAX_TOTAL_REPORTS = int(os.getenv("RESEARCH_REPORTS_MAX_TOTAL", "48"))
MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(16 * 1024 * 1024)))
MAX_ARCHIVE_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_ARCHIVE_BYTES", str(120 * 1024 * 1024)))
MAX_SEARCH_RESULTS = int(os.getenv("RESEARCH_REPORT_SEARCH_RESULTS", "10"))
LOOKBACK_DAYS = int(os.getenv("RESEARCH_REPORT_LOOKBACK_DAYS", "1095"))
WORKERS = max(1, min(6, int(os.getenv("RESEARCH_REPORT_WORKERS", "4"))))
SUPPORTED_MARKETS = {"A股", "港股", "美股"}
US_TICKER = re.compile(r"^[A-Z][A-Z0-9.-]{0,14}$")
PDF_KEYWORDS = (
    "研报",
    "研究报告",
    "公司深度",
    "深度报告",
    "行业研究",
    "招股书",
    "年报",
    "年度报告",
    "业绩演示",
    "投资者演示",
    "research report",
    "equity research",
    "initiation",
    "deep dive",
    "investor presentation",
    "earnings presentation",
    "annual report",
    "prospectus",
    "fact sheet",
)
EXCLUDED_HOST_PARTS = (
    "scribd.com",
    "docin.com",
    "wenku.baidu.com",
    "pan.baidu.com",
    "drive.google.com",
)


def log(message: str) -> None:
    print(f"RESEARCH_REPORT: {message}", flush=True)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def clean_text(value: Any, limit: int = 240) -> str:
    text = html.unescape(re.sub(r"\s+", " ", str(value or ""))).strip()
    return text[:limit]


def safe_slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return normalized or hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def canonical_url(value: str) -> str:
    return value.strip().replace("&amp;", "&")


def request_bytes(
    url: str,
    *,
    timeout: int = 35,
    max_bytes: int | None = None,
    referer: str = "https://www.bing.com/",
) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": referer,
            "Accept": "application/json,text/xml,application/rss+xml,text/plain,*/*"
            if "reportapi" in url or "format=rss" in url
            else "application/pdf,text/html,*/*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urlopen(request, timeout=timeout) as response:
                content_length = int(response.headers.get("Content-Length") or 0)
                if max_bytes and content_length > max_bytes:
                    raise ValueError(f"response too large: {content_length}")
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = response.read(128 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if max_bytes and total > max_bytes:
                        raise ValueError(f"response exceeded {max_bytes} bytes")
                    chunks.append(chunk)
                return b"".join(chunks)
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            last_error = error
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last_error}")


def parse_json_or_jsonp(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\((\{[\s\S]*\})\)\s*;?\s*$", text)
    if not match:
        raise ValueError("unexpected research report response")
    return json.loads(match.group(1))


def split_people(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [item for item in re.split(r"[,，、;/\s]+", text) if item][:8]


def parse_date(value: Any) -> str:
    raw = clean_text(value)
    match = re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", raw)
    if match:
        parts = re.split(r"[-/.]", match.group(0))
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc).date().isoformat()


def report_date(record: dict[str, Any]) -> str:
    return parse_date(
        record.get("publishDate")
        or record.get("publishTime")
        or record.get("date")
        or record.get("updateTime")
    )


def record_info_code(record: dict[str, Any]) -> str:
    return clean_text(
        record.get("infoCode") or record.get("infocode") or record.get("info_code"),
        96,
    )


def normalize_ticker(value: Any, market: str) -> str:
    text = clean_text(value, 40).upper().replace(" ", "")
    if market == "A股":
        digits = re.sub(r"\D", "", text)
        return digits if len(digits) == 6 else ""
    if market == "港股":
        text = text.removeprefix("HK").removesuffix(".HK")
        digits = re.sub(r"\D", "", text)
        return digits.zfill(5) if 1 <= len(digits) <= 5 else ""
    if market == "美股":
        return text if US_TICKER.fullmatch(text) else ""
    return ""


def normalize_company(raw: dict[str, Any]) -> dict[str, str] | None:
    market = clean_text(raw.get("market"), 20)
    if raw.get("enabled") is False or market not in SUPPORTED_MARKETS:
        return None
    ticker = normalize_ticker(raw.get("ticker"), market)
    name = clean_text(raw.get("name"), 120)
    if not ticker or not name:
        return None
    company_id = clean_text(raw.get("id"), 120)
    slug = clean_text(raw.get("catalogSlug") or company_id, 120)
    if not slug:
        slug = f"{market}-{safe_slug(ticker)}"
    return {
        "id": company_id,
        "slug": slug,
        "name": name,
        "ticker": ticker,
        "market": market,
        "sector": clean_text(raw.get("sector") or "未分类", 80),
    }


def company_aliases(company: dict[str, str]) -> list[str]:
    values = [company["name"], company["ticker"]]
    if company["market"] == "港股":
        values.extend([company["ticker"].lstrip("0"), f"HK{company['ticker']}"])
    return [value for value in dict.fromkeys(values) if value]


def load_company_websites() -> dict[str, str]:
    snapshot = read_json(MARKET_PROFILE_PATH, {})
    profiles = snapshot.get("profiles") if isinstance(snapshot, dict) else {}
    if not isinstance(profiles, dict):
        return {}
    result: dict[str, str] = {}
    for slug, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        company = profile.get("company")
        website = clean_text(company.get("website") if isinstance(company, dict) else "", 500)
        if website.startswith(("http://", "https://")):
            result[str(slug)] = website
    return result


def eastmoney_ticker_variants(company: dict[str, str]) -> list[str]:
    ticker = company["ticker"]
    if company["market"] == "A股":
        return [ticker]
    if company["market"] == "港股":
        return [ticker, ticker.lstrip("0"), f"HK{ticker}", f"{ticker}.HK"]
    return [ticker]


def fetch_eastmoney_reports(company: dict[str, str]) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    begin = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    combined: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ticker_variant in eastmoney_ticker_variants(company):
        params = {
            "industryCode": "*",
            "pageSize": "40",
            "industry": "*",
            "rating": "*",
            "ratingChange": "*",
            "beginTime": begin,
            "endTime": end,
            "pageNo": "1",
            "fields": "",
            "qType": "0",
            "orgCode": "",
            "code": ticker_variant,
            "rcode": "",
            "p": "1",
            "pageNum": "1",
            "pageNumber": "1",
        }
        try:
            payload = parse_json_or_jsonp(
                request_bytes(
                    f"{REPORT_API}?{urlencode(params)}",
                    referer="https://data.eastmoney.com/report/index",
                )
            )
        except Exception as error:
            log(f"{company['ticker']} Eastmoney {ticker_variant} failed: {error}")
            continue
        data = payload.get("data")
        if not isinstance(data, list):
            result = payload.get("result") or payload.get("Result") or {}
            data = result.get("data") if isinstance(result, dict) else []
        for record in data if isinstance(data, list) else []:
            if not isinstance(record, dict) or not record_matches_company(record, company):
                continue
            key = record_info_code(record) or clean_text(record.get("title"), 320)
            if key and key not in seen:
                seen.add(key)
                combined.append(record)
        if combined:
            break
    return combined


def record_matches_company(record: dict[str, Any], company: dict[str, str]) -> bool:
    code = clean_text(
        record.get("stockCode")
        or record.get("stockcode")
        or record.get("secuCode")
        or record.get("code"),
        40,
    )
    if code:
        normalized = normalize_ticker(code, company["market"])
        if normalized and normalized != company["ticker"]:
            return False
    stock_name = clean_text(record.get("stockName") or record.get("securityName"), 120)
    if stock_name and company["name"] not in stock_name and stock_name not in company["name"]:
        if company["ticker"] not in clean_text(record, 1000):
            return False
    return True


def validate_pdf(data: bytes) -> None:
    if len(data) < 1024:
        raise ValueError("PDF response is too small")
    if not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("response is not a PDF")
    if b"%%EOF" not in data[-8192:]:
        raise ValueError("PDF EOF marker missing")


def write_pdf(filename: str, data: bytes) -> tuple[str, int]:
    validate_pdf(data)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    target = PDF_DIR / filename
    if target.exists() and target.stat().st_size == len(data):
        return f"/research-reports/{filename}", len(data)
    with tempfile.NamedTemporaryFile(dir=PDF_DIR, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(target)
    return f"/research-reports/{filename}", len(data)


def archive_eastmoney_pdf(info_code: str) -> tuple[str, int, str]:
    slug = f"eastmoney-{safe_slug(info_code)}"
    filename = f"{slug}.pdf"
    target = PDF_DIR / filename
    url = PDF_TEMPLATE.format(info_code=info_code)
    if target.exists() and target.stat().st_size > 1024:
        data = target.read_bytes()
        validate_pdf(data)
        return f"/research-reports/{filename}", len(data), url
    data = request_bytes(
        url,
        max_bytes=MAX_PDF_BYTES,
        referer="https://data.eastmoney.com/report/index",
    )
    local_url, size = write_pdf(filename, data)
    return local_url, size, url


def build_eastmoney_report(
    record: dict[str, Any], company: dict[str, str]
) -> dict[str, Any] | None:
    info_code = record_info_code(record)
    title = clean_text(record.get("title") or record.get("reportTitle"), 320)
    if not info_code or not title:
        return None
    local_url, file_size, pdf_url = archive_eastmoney_pdf(info_code)
    institution = clean_text(
        record.get("orgSName")
        or record.get("orgName")
        or record.get("organization")
        or "研究机构",
        120,
    )
    rating = clean_text(
        record.get("emRatingName") or record.get("ratingName") or record.get("rating"),
        40,
    )
    rating_change = clean_text(
        record.get("ratingChange") or record.get("ratingChangeName"), 40
    )
    details = [institution, f"关联 {company['name']}（{company['ticker']}）"]
    if rating:
        details.append(f"评级 {rating}")
    return {
        "id": info_code,
        "slug": f"eastmoney-{safe_slug(info_code)}",
        "title": title,
        "publishedAt": report_date(record),
        "institution": institution,
        "analysts": split_people(record.get("researcher") or record.get("author")),
        "reportType": classify_report(title),
        "companySlug": company["slug"],
        "companyName": clean_text(record.get("stockName") or company["name"], 120),
        "ticker": company["ticker"],
        "market": company["market"],
        "sector": clean_text(record.get("industryName") or company["sector"], 80),
        "rating": rating or None,
        "ratingChange": rating_change or None,
        "summary": " · ".join(details) + "。点击进入站内 PDF 阅读。",
        "sourceName": "东方财富研报中心",
        "sourcePageUrl": f"https://data.eastmoney.com/report/stock.jshtml?stockcode={company['ticker']}",
        "originalPdfUrl": pdf_url,
        "localPdfUrl": local_url,
        "fileSizeBytes": file_size,
        "archivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def classify_report(title: str) -> str:
    lowered = title.casefold()
    if any(value in lowered for value in ("招股书", "prospectus")):
        return "招股书"
    if any(value in lowered for value in ("年报", "年度报告", "annual report")):
        return "年度报告"
    if any(
        value in lowered
        for value in ("业绩演示", "投资者演示", "investor presentation", "earnings presentation")
    ):
        return "投资者演示"
    if any(value in lowered for value in ("行业", "industry", "sector")):
        return "行业研报"
    return "个股研报"


def bing_queries(company: dict[str, str], website: str) -> list[str]:
    name = company["name"]
    ticker = company["ticker"]
    if company["market"] == "美股":
        queries = [
            f'"{name}" "{ticker}" ("equity research" OR "investor presentation" OR "annual report") filetype:pdf',
            f'"{name}" ("research report" OR "earnings presentation" OR prospectus) filetype:pdf',
        ]
    elif company["market"] == "港股":
        queries = [
            f'"{name}" "{ticker}" (研报 OR 研究报告 OR 招股书 OR 业绩演示) filetype:pdf',
            f'"{name}" (annual report OR investor presentation OR research) filetype:pdf',
        ]
    else:
        queries = [
            f'"{name}" "{ticker}" (研报 OR 公司深度 OR 研究报告) filetype:pdf',
            f'"{name}" (行业研究 OR 年报 OR 业绩演示) filetype:pdf',
        ]
    if website:
        host = urlparse(website).netloc.removeprefix("www.")
        if host:
            queries.insert(
                0,
                f'site:{host} "{name}" ("investor presentation" OR "annual report" OR 业绩演示 OR 年报) filetype:pdf',
            )
    return queries[:3]


def unwrap_search_url(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    for key in ("url", "r", "target"):
        candidate = query.get(key, [""])[0]
        if candidate.startswith(("http://", "https://")):
            return candidate
    return url


def parse_bing_rss(raw: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(raw.decode("utf-8", errors="replace"))
    items: list[dict[str, str]] = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title"), 320)
        link = canonical_url(unwrap_search_url(clean_text(item.findtext("link"), 800)))
        description = clean_text(item.findtext("description"), 500)
        published = clean_text(item.findtext("pubDate"), 100)
        if title and link.startswith(("http://", "https://")):
            items.append(
                {
                    "title": title,
                    "url": link,
                    "description": description,
                    "publishedAt": parse_date(published),
                }
            )
    return items


def discover_public_pdf_candidates(
    company: dict[str, str], website: str
) -> list[dict[str, str]]:
    return discover_web_candidates(
        company,
        website,
        request_bytes,
        max_results=MAX_SEARCH_RESULTS,
    )


def is_research_candidate(
    item: dict[str, str], company: dict[str, str], website: str
) -> bool:
    url = item["url"]
    parsed = urlparse(url)
    host = parsed.netloc.casefold().removeprefix("www.")
    if not host or any(part in host for part in EXCLUDED_HOST_PARTS):
        return False
    combined = f"{item.get('title', '')} {item.get('description', '')} {url}".casefold()
    has_pdf_signal = ".pdf" in parsed.path.casefold() or "pdf" in combined
    if not has_pdf_signal:
        return False
    keyword_hit = any(keyword.casefold() in combined for keyword in PDF_KEYWORDS)
    alias_hit = any(alias.casefold() in combined for alias in company_aliases(company))
    website_host = urlparse(website).netloc.casefold().removeprefix("www.") if website else ""
    trusted_company_host = bool(website_host and (host == website_host or host.endswith(f".{website_host}")))
    return (keyword_hit and alias_hit) or (trusted_company_host and keyword_hit)


def source_name_from_url(url: str) -> str:
    host = urlparse(url).netloc.removeprefix("www.")
    return host or "公开 PDF 来源"


def archive_public_report(
    candidate: dict[str, str], company: dict[str, str]
) -> dict[str, Any]:
    url = canonical_url(candidate["url"])
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]
    slug = f"public-{digest}"
    filename = f"{slug}.pdf"
    target = PDF_DIR / filename
    if target.exists() and target.stat().st_size > 1024:
        data = target.read_bytes()
        validate_pdf(data)
        local_url = f"/research-reports/{filename}"
        size = len(data)
    else:
        data = request_bytes(url, max_bytes=MAX_PDF_BYTES, referer="https://www.bing.com/")
        local_url, size = write_pdf(filename, data)
    title = clean_text(candidate.get("title") or f"{company['name']} 公开研究资料", 320)
    institution = source_name_from_url(url)
    return {
        "id": slug,
        "slug": slug,
        "title": title,
        "publishedAt": candidate.get("publishedAt") or datetime.now(timezone.utc).date().isoformat(),
        "institution": institution,
        "analysts": [],
        "reportType": classify_report(title),
        "companySlug": company["slug"],
        "companyName": company["name"],
        "ticker": company["ticker"],
        "market": company["market"],
        "sector": company["sector"],
        "rating": None,
        "ratingChange": None,
        "summary": f"{institution} · 关联 {company['name']}（{company['ticker']}）。点击进入站内 PDF 阅读。",
        "sourceName": institution,
        "sourcePageUrl": url,
        "originalPdfUrl": url,
        "localPdfUrl": local_url,
        "fileSizeBytes": size,
        "archivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def crawl_company(
    company: dict[str, str],
    website: str,
    cik: str,
    previous_reports: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    new_reports: list[dict[str, Any]] = []
    errors: list[str] = []
    fetched = 0

    try:
        eastmoney_records = fetch_eastmoney_reports(company)
        fetched += len(eastmoney_records)
        for record in eastmoney_records:
            try:
                report = build_eastmoney_report(record, company)
            except Exception as error:
                errors.append(f"Eastmoney PDF: {error}")
                continue
            if report:
                new_reports.append(report)
            if len(new_reports) >= MAX_REPORTS_PER_COMPANY:
                break
    except Exception as error:
        errors.append(f"Eastmoney: {error}")

    if len(new_reports) < MAX_REPORTS_PER_COMPANY and cik:
        sec_candidates = discover_sec_candidates(company, cik, request_bytes)
        fetched += len(sec_candidates)
        for candidate in sec_candidates:
            try:
                report = archive_public_report(candidate, company)
            except Exception as error:
                errors.append(f"SEC PDF {candidate.get('url', '')}: {error}")
                continue
            new_reports.append(report)
            if len(new_reports) >= MAX_REPORTS_PER_COMPANY:
                break

    if len(new_reports) < MAX_REPORTS_PER_COMPANY:
        candidates = discover_public_pdf_candidates(company, website)
        fetched += len(candidates)
        for candidate in candidates:
            try:
                report = archive_public_report(candidate, company)
            except Exception as error:
                errors.append(f"public PDF {candidate.get('url', '')}: {error}")
                continue
            new_reports.append(report)
            if len(new_reports) >= MAX_REPORTS_PER_COMPANY:
                break

    merged: dict[str, dict[str, Any]] = {}
    for report in [*new_reports, *previous_reports]:
        report_id = clean_text(report.get("id"), 160)
        if report_id and report_id not in merged:
            merged[report_id] = report
    reports = sorted(
        merged.values(), key=lambda report: report.get("publishedAt", ""), reverse=True
    )[:MAX_REPORTS_PER_COMPANY]
    status = "ok" if new_reports else ("retained" if reports else "empty")
    return reports, {
        "source": f"多源公开 PDF · {company['name']} {company['ticker']}",
        "companySlug": company["slug"],
        "market": company["market"],
        "status": status,
        "fetched": fetched,
        "archived": len(new_reports),
        "retained": max(0, len(reports) - len(new_reports)),
        "adapters": [
            "Eastmoney",
            *( ["SEC"] if cik else [] ),
            "public-web",
            *( ["company-domain"] if website else [] ),
        ],
        **({"errors": errors[:5]} if errors else {}),
    }


def main() -> int:
    config = read_json(CONFIG_PATH, {})
    previous = read_json(INDEX_PATH, {"reports": []})
    websites = merge_source_maps(
        load_company_websites(),
        load_official_websites(ROOT),
    )
    sec_tickers = merge_source_maps(
        load_sec_ticker_map(request_bytes),
        load_local_cik_map(ROOT),
    )
    companies = [
        company
        for raw in config.get("listedCompanies", [])
        if isinstance(raw, dict) and (company := normalize_company(raw))
    ]
    previous_by_company: dict[str, list[dict[str, Any]]] = {}
    for report in previous.get("reports", []):
        if isinstance(report, dict) and report.get("companySlug"):
            previous_by_company.setdefault(str(report["companySlug"]), []).append(report)

    collected: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {
            executor.submit(
                crawl_company,
                company,
                websites.get(company["slug"], ""),
                sec_tickers.get(company["ticker"], ""),
                previous_by_company.get(company["slug"], []),
            ): company
            for company in companies
        }
        for future in as_completed(futures):
            company = futures[future]
            try:
                reports, status = future.result()
            except Exception as error:
                log(f"{company['ticker']} unexpected failure: {error}")
                reports = previous_by_company.get(company["slug"], [])[:MAX_REPORTS_PER_COMPANY]
                status = {
                    "source": f"多源公开 PDF · {company['name']} {company['ticker']}",
                    "companySlug": company["slug"],
                    "market": company["market"],
                    "status": "retained" if reports else "failed",
                    "fetched": 0,
                    "archived": 0,
                    "retained": len(reports),
                    "errors": [str(error)[:300]],
                }
            collected.extend(reports)
            statuses.append(status)

    unique = {report["id"]: report for report in collected if report.get("id")}
    ordered_reports = sorted(
        unique.values(), key=lambda report: report.get("publishedAt", ""), reverse=True
    )[:MAX_TOTAL_REPORTS]
    reports: list[dict[str, Any]] = []
    archive_bytes = 0
    for report in ordered_reports:
        file_size = int(report.get("fileSizeBytes") or 0)
        if reports and file_size > 0 and archive_bytes + file_size > MAX_ARCHIVE_BYTES:
            continue
        reports.append(report)
        archive_bytes += max(0, file_size)
    referenced = {
        Path(report["localPdfUrl"]).name
        for report in reports
        if report.get("localPdfUrl")
    }
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for path in PDF_DIR.glob("*.pdf"):
        if path.name.startswith(("eastmoney-", "public-")) and path.name not in referenced:
            path.unlink()

    market_counts = {
        market: sum(1 for company in companies if company["market"] == market)
        for market in sorted(SUPPORTED_MARKETS)
    }
    payload = {
        "schemaVersion": 3,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trackedCompanies": len(companies),
        "marketCounts": market_counts,
        "archiveBytes": archive_bytes,
        "reports": reports,
        "sourceStatus": sorted(statuses, key=lambda item: (item.get("market", ""), item.get("source", ""))),
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    log(
        f"archived {len(reports)} validated PDF report(s) for "
        f"{len(companies)} enabled listed companies across {market_counts}"
    )
    return 0 if len(statuses) == len(companies) else 1


if __name__ == "__main__":
    raise SystemExit(main())
