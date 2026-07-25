#!/usr/bin/env python3
"""Public PDF discovery adapters used by the listed-company report crawler."""

from __future__ import annotations

import html
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import parse_qs, quote_plus, urljoin, urlparse

BING_RSS = "https://www.bing.com/search?format=rss&q={query}"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBMISSIONS = "https://data.sec.gov/submissions/CIK{cik}.json"
PDF_TERMS = (
    "research",
    "report",
    "presentation",
    "shareholder letter",
    "annual",
    "prospectus",
    "results",
    "earnings",
    "研报",
    "研究",
    "报告",
    "招股书",
    "年报",
    "业绩",
    "演示",
)
REJECT_TERMS = (
    "certificate",
    "certification",
    "privacy policy",
    "terms of use",
    "code of conduct",
    "supplier policy",
    "iso 9001",
    "press release pdf",
    "news release pdf",
    "proxy card",
    "form of proxy",
    "monthly return",
    "notice of meeting",
    "证书",
    "认证证书",
    "隐私政策",
    "使用条款",
    "月报表",
    "代表委任表格",
    "会议通知",
)
LANDING_TERMS = (
    "investor",
    "financial",
    "presentation",
    "reports",
    "results",
    "filings",
    "annual",
    "hkexnews",
    "research",
)
EXCLUDED_HOSTS = (
    "scribd.com",
    "docin.com",
    "wenku.baidu.com",
    "pan.baidu.com",
    "drive.google.com",
)

RequestBytes = Callable[..., bytes]


def clean(value: Any, limit: int = 600) -> str:
    return html.unescape(re.sub(r"\s+", " ", str(value or ""))).strip()[:limit]


def strip_tags(value: str) -> str:
    return clean(re.sub(r"<[^>]+>", " ", value), 500)


def parse_date(value: Any) -> str:
    raw = clean(value, 120)
    match = re.search(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", raw)
    if match:
        parts = re.split(r"[-/.]", match.group(0))
        return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}"
    try:
        return parsedate_to_datetime(raw).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        return datetime.now(timezone.utc).date().isoformat()


def aliases(company: dict[str, str]) -> list[str]:
    values = [company.get("name", ""), company.get("ticker", "")]
    if company.get("market") == "港股":
        ticker = company.get("ticker", "")
        values.extend([ticker.lstrip("0"), f"HK{ticker}"])
    return [value for value in dict.fromkeys(values) if value]


def host_name(url: str) -> str:
    return urlparse(url).netloc.casefold().removeprefix("www.")


def company_host(website: str) -> str:
    host = host_name(website)
    parts = host.split(".")
    if len(parts) > 2 and parts[0] in {"ir", "investor", "investors", "www"}:
        return ".".join(parts[1:])
    return host


def is_company_domain(url: str, website: str) -> bool:
    target = host_name(url)
    root = company_host(website)
    return bool(root and (target == root or target.endswith(f".{root}")))


def unwrap_search_url(url: str) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    for key in ("url", "r", "target"):
        candidate = params.get(key, [""])[0]
        if candidate.startswith(("http://", "https://")):
            return candidate
    return url


def parse_bing_rss(raw: bytes) -> list[dict[str, str]]:
    root = ET.fromstring(raw.decode("utf-8", errors="replace"))
    items: list[dict[str, str]] = []
    for node in root.findall(".//item"):
        title = clean(node.findtext("title"), 320)
        url = clean(unwrap_search_url(node.findtext("link") or ""), 1000)
        if not title or not url.startswith(("http://", "https://")):
            continue
        items.append(
            {
                "title": title,
                "url": url.replace("&amp;", "&"),
                "description": strip_tags(node.findtext("description") or ""),
                "publishedAt": parse_date(node.findtext("pubDate")),
            }
        )
    return items


def simple_queries(company: dict[str, str], website: str) -> list[str]:
    name = company["name"]
    ticker = company["ticker"]
    market = company["market"]
    queries: list[str] = []
    root = company_host(website)
    if root:
        queries.extend(
            [
                f"site:{root} {ticker} investor presentation pdf",
                f"site:{root} {name} annual report pdf",
            ]
        )
    if market == "美股":
        queries.extend(
            [
                f"{name} {ticker} investor presentation pdf",
                f"{name} {ticker} annual report pdf",
                f"site:annualreports.com/HostedData/AnnualReportArchive {ticker} pdf",
            ]
        )
    elif market == "港股":
        queries.extend(
            [
                f"site:hkexnews.hk {ticker} Annual Report",
                f"site:hkexnews.hk {ticker} prospectus",
                f"{name} {ticker} investor presentation pdf",
            ]
        )
    else:
        queries.extend(
            [
                f"{name} {ticker} 公司深度 研报 pdf",
                f"{name} {ticker} 年报 业绩演示 pdf",
            ]
        )
    return list(dict.fromkeys(queries))[:6]


def is_direct_pdf(url: str) -> bool:
    parsed = urlparse(url)
    combined = f"{parsed.path} {parsed.query}".casefold()
    return ".pdf" in combined


def is_rejected_text(text: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in REJECT_TERMS)


def is_relevant_text(text: str, company: dict[str, str]) -> bool:
    lowered = text.casefold()
    if is_rejected_text(lowered):
        return False
    term_hit = any(term.casefold() in lowered for term in PDF_TERMS)
    alias_hit = any(alias.casefold() in lowered for alias in aliases(company))
    return term_hit and alias_hit


def relevant_landing(item: dict[str, str], company: dict[str, str], website: str) -> bool:
    url = item["url"]
    host = host_name(url)
    if not host or any(value in host for value in EXCLUDED_HOSTS):
        return False
    combined = f"{item.get('title', '')} {item.get('description', '')} {url}".casefold()
    if is_company_domain(url, website):
        return any(term in combined for term in LANDING_TERMS)
    if "hkexnews.hk" in host and company.get("market") == "港股":
        return any(alias.casefold() in combined for alias in aliases(company))
    if "annualreports.com" in host and company.get("market") == "美股":
        return any(alias.casefold() in combined for alias in aliases(company))
    return is_relevant_text(combined, company)


def extract_pdf_links(
    page_url: str,
    raw: bytes,
    company: dict[str, str],
    website: str,
) -> list[dict[str, str]]:
    text = raw.decode("utf-8", errors="replace")
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()

    for match in re.finditer(
        r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>([\s\S]*?)</a>",
        text,
        re.IGNORECASE,
    ):
        href = html.unescape(match.group(1)).replace("\\/", "/")
        anchor = strip_tags(match.group(2))
        url = urljoin(page_url, href)
        if not is_direct_pdf(url) or url in seen:
            continue
        context_start = max(0, match.start() - 240)
        context_end = min(len(text), match.end() + 240)
        context = strip_tags(text[context_start:context_end])
        combined = f"{anchor} {context} {url}"
        if is_rejected_text(combined) or not (
            is_relevant_text(combined, company)
            or (is_company_domain(url, website) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("hkexnews.hk" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("sec.gov" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
        ):
            continue
        seen.add(url)
        candidates.append(
            {
                "title": anchor or f"{company['name']} 公开研究资料",
                "url": url,
                "description": context,
                "publishedAt": parse_date(context),
            }
        )

    escaped = text.replace("\\/", "/")
    for url in re.findall(r"https?://[^\"'<>\s]+?\.pdf(?:\?[^\"'<>\s]*)?", escaped, re.IGNORECASE):
        url = html.unescape(url)
        if url in seen:
            continue
        window_at = escaped.find(url)
        context = strip_tags(escaped[max(0, window_at - 300): window_at + len(url) + 300])
        combined = context + " " + url
        if is_rejected_text(combined) or not (
            is_relevant_text(combined, company)
            or (
                (is_company_domain(url, website) or "hkexnews.hk" in host_name(url) or "sec.gov" in host_name(url))
                and any(term in combined.casefold() for term in PDF_TERMS)
            )
        ):
            continue
        seen.add(url)
        candidates.append(
            {
                "title": clean(context, 220) or f"{company['name']} 公开研究资料",
                "url": url,
                "description": context,
                "publishedAt": parse_date(context),
            }
        )
    return candidates


def ir_seed_pages(website: str) -> list[str]:
    if not website:
        return []
    parsed = urlparse(website)
    root = company_host(website)
    scheme = parsed.scheme or "https"
    seeds = [website]
    if root:
        seeds.extend(
            [
                f"{scheme}://investors.{root}/",
                f"{scheme}://ir.{root}/",
                f"{scheme}://{root}/investors/",
                f"{scheme}://{root}/investor-relations/",
                f"{scheme}://{root}/financials/annual-reports/",
                f"{scheme}://{root}/events-and-presentations/",
                f"{scheme}://{root}/news-events/presentations/",
            ]
        )
    return list(dict.fromkeys(seeds))[:8]


def discover_web_candidates(
    company: dict[str, str],
    website: str,
    request_bytes: RequestBytes,
    *,
    max_results: int = 14,
) -> list[dict[str, str]]:
    direct: list[dict[str, str]] = []
    landing_pages: list[str] = []
    seen_urls: set[str] = set()

    for seed in ir_seed_pages(website):
        landing_pages.append(seed)

    for query in simple_queries(company, website):
        try:
            raw = request_bytes(BING_RSS.format(query=quote_plus(query)), timeout=25)
            items = parse_bing_rss(raw)
        except Exception:
            continue
        for item in items:
            url = item["url"]
            if url in seen_urls:
                continue
            seen_urls.add(url)
            if is_direct_pdf(url):
                if is_relevant_text(
                    f"{item.get('title', '')} {item.get('description', '')} {url}",
                    company,
                ) or is_company_domain(url, website) or "hkexnews.hk" in host_name(url):
                    direct.append(item)
            elif relevant_landing(item, company, website):
                landing_pages.append(url)

    for page_url in list(dict.fromkeys(landing_pages))[:10]:
        try:
            raw = request_bytes(page_url, timeout=22, max_bytes=3 * 1024 * 1024, referer=website or "https://www.bing.com/")
        except Exception:
            continue
        for item in extract_pdf_links(page_url, raw, company, website):
            if item["url"] not in seen_urls:
                seen_urls.add(item["url"])
                direct.append(item)
                if len(direct) >= max_results:
                    return direct
    return direct[:max_results]


def load_sec_ticker_map(request_bytes: RequestBytes) -> dict[str, str]:
    try:
        raw = request_bytes(
            SEC_TICKERS,
            timeout=30,
            max_bytes=5 * 1024 * 1024,
            referer="https://www.sec.gov/",
        )
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return {}
    result: dict[str, str] = {}
    for item in payload.values() if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        ticker = clean(item.get("ticker"), 20).upper()
        cik = str(item.get("cik_str") or "").zfill(10)
        if ticker and cik.isdigit():
            result[ticker] = cik
    return result


def discover_sec_candidates(
    company: dict[str, str],
    cik: str,
    request_bytes: RequestBytes,
) -> list[dict[str, str]]:
    if company.get("market") != "美股" or not cik:
        return []
    try:
        raw = request_bytes(
            SEC_SUBMISSIONS.format(cik=cik),
            timeout=30,
            max_bytes=12 * 1024 * 1024,
            referer="https://www.sec.gov/",
        )
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return []
    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, dict) else {}
    if not isinstance(recent, dict):
        return []
    forms = recent.get("form") or []
    documents = recent.get("primaryDocument") or []
    accessions = recent.get("accessionNumber") or []
    dates = recent.get("filingDate") or []
    descriptions = recent.get("primaryDocDescription") or []
    items: list[dict[str, str]] = []
    for index, form in enumerate(forms):
        if index >= len(documents) or index >= len(accessions):
            break
        document = clean(documents[index], 300)
        if not document.casefold().endswith(".pdf"):
            continue
        form = clean(form, 30)
        if form not in {"ARS", "DEF 14A", "425", "8-K", "6-K", "20-F"}:
            continue
        accession = re.sub(r"\D", "", str(accessions[index]))
        url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}/{document}"
        description = clean(descriptions[index] if index < len(descriptions) else "", 240)
        date = clean(dates[index] if index < len(dates) else "", 40)
        items.append(
            {
                "title": description or f"{company['name']} {form} {date}",
                "url": url,
                "description": f"SEC {form} · {company['name']}",
                "publishedAt": parse_date(date),
            }
        )
        if len(items) >= 5:
            break
    return items
