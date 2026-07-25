#!/usr/bin/env python3
"""Build a bounded, attributable archive of publicly downloadable research PDFs.

The crawler currently uses Eastmoney's public research-report endpoint for tracked
A-share companies. It does not authenticate, bypass paywalls, or scrape protected
report bodies. Only responses that validate as PDF files are committed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
INDEX_PATH = ROOT / "public" / "data" / "research_reports.json"
PDF_DIR = ROOT / "public" / "research-reports"
REPORT_API = "https://reportapi.eastmoney.com/report/list"
PDF_TEMPLATE = "https://pdf.dfcfw.com/pdf/H3_{info_code}_1.pdf"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)
MAX_REPORTS_PER_COMPANY = int(os.getenv("RESEARCH_REPORTS_PER_COMPANY", "2"))
MAX_TOTAL_REPORTS = int(os.getenv("RESEARCH_REPORTS_MAX_TOTAL", "24"))
MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(12 * 1024 * 1024)))
LOOKBACK_DAYS = int(os.getenv("RESEARCH_REPORT_LOOKBACK_DAYS", "730"))


def log(message: str) -> None:
    print(f"RESEARCH_REPORT: {message}", flush=True)


def read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return fallback


def request_bytes(url: str, *, timeout: int = 35, max_bytes: int | None = None) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://data.eastmoney.com/report/index",
            "Accept": "application/json,text/plain,*/*" if "reportapi" in url else "application/pdf,*/*",
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
                time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"request failed: {url}: {last_error}")


def parse_json_or_jsonp(raw: bytes) -> dict[str, Any]:
    text = raw.decode("utf-8", errors="replace").strip()
    if text.startswith("{"):
        return json.loads(text)
    match = re.search(r"\((\{[\s\S]*\})\)\s*;?\s*$", text)
    if not match:
        raise ValueError("unexpected research report response")
    return json.loads(match.group(1))


def fetch_company_reports(ticker: str) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    begin = (now - timedelta(days=LOOKBACK_DAYS)).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
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
        "code": ticker,
        "rcode": "",
        "p": "1",
        "pageNum": "1",
        "pageNumber": "1",
    }
    payload = parse_json_or_jsonp(request_bytes(f"{REPORT_API}?{urlencode(params)}"))
    data = payload.get("data")
    if not isinstance(data, list):
        result = payload.get("result") or payload.get("Result") or {}
        data = result.get("data") if isinstance(result, dict) else []
    return data if isinstance(data, list) else []


def clean_text(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit]


def split_people(value: Any) -> list[str]:
    text = clean_text(value)
    if not text:
        return []
    return [item for item in re.split(r"[,，、;/\s]+", text) if item][:8]


def report_date(record: dict[str, Any]) -> str:
    raw = clean_text(
        record.get("publishDate")
        or record.get("publishTime")
        or record.get("date")
        or record.get("updateTime")
    )
    match = re.search(r"\d{4}-\d{2}-\d{2}", raw)
    return match.group(0) if match else datetime.now(timezone.utc).date().isoformat()


def record_info_code(record: dict[str, Any]) -> str:
    return clean_text(record.get("infoCode") or record.get("infocode") or record.get("info_code"), 96)


def safe_slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return normalized or hashlib.sha256(value.encode("utf-8")).hexdigest()[:20]


def validate_pdf(data: bytes) -> None:
    if len(data) < 1024:
        raise ValueError("PDF response is too small")
    if not data.lstrip().startswith(b"%PDF-"):
        raise ValueError("response is not a PDF")
    if b"%%EOF" not in data[-4096:]:
        raise ValueError("PDF EOF marker missing")


def archive_pdf(info_code: str) -> tuple[str, int, str]:
    slug = f"eastmoney-{safe_slug(info_code)}"
    filename = f"{slug}.pdf"
    target = PDF_DIR / filename
    url = PDF_TEMPLATE.format(info_code=info_code)
    if target.exists() and target.stat().st_size > 1024:
        data = target.read_bytes()
        validate_pdf(data)
        return f"/research-reports/{filename}", len(data), url
    data = request_bytes(url, max_bytes=MAX_PDF_BYTES)
    validate_pdf(data)
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=PDF_DIR, delete=False) as handle:
        handle.write(data)
        temporary = Path(handle.name)
    temporary.replace(target)
    return f"/research-reports/{filename}", len(data), url


def normalize_company(raw: dict[str, Any]) -> dict[str, str] | None:
    if not raw.get("enabled", True) or raw.get("market") != "A股":
        return None
    ticker = re.sub(r"\D", "", str(raw.get("ticker") or ""))
    if len(ticker) != 6:
        return None
    return {
        "id": clean_text(raw.get("id"), 120),
        "slug": clean_text(raw.get("catalogSlug") or raw.get("id"), 120),
        "name": clean_text(raw.get("name"), 120),
        "ticker": ticker,
        "market": "A股",
        "sector": clean_text(raw.get("sector") or "未分类", 80),
    }


def build_report(record: dict[str, Any], company: dict[str, str]) -> dict[str, Any] | None:
    info_code = record_info_code(record)
    title = clean_text(record.get("title") or record.get("reportTitle"), 320)
    if not info_code or not title:
        return None
    local_url, file_size, pdf_url = archive_pdf(info_code)
    institution = clean_text(
        record.get("orgSName") or record.get("orgName") or record.get("organization") or "研究机构",
        120,
    )
    rating = clean_text(record.get("emRatingName") or record.get("ratingName") or record.get("rating"), 40)
    rating_change = clean_text(record.get("ratingChange") or record.get("ratingChangeName"), 40)
    details = [institution, f"关联 {company['name']}（{company['ticker']}）"]
    if rating:
        details.append(f"评级 {rating}")
    summary = " · ".join(details) + "。点击进入站内 PDF 阅读。"
    slug = f"eastmoney-{safe_slug(info_code)}"
    return {
        "id": info_code,
        "slug": slug,
        "title": title,
        "publishedAt": report_date(record),
        "institution": institution,
        "analysts": split_people(record.get("researcher") or record.get("author")),
        "reportType": "个股研报",
        "companySlug": company["slug"],
        "companyName": clean_text(record.get("stockName") or company["name"], 120),
        "ticker": company["ticker"],
        "market": company["market"],
        "sector": clean_text(record.get("industryName") or company["sector"], 80),
        "rating": rating or None,
        "ratingChange": rating_change or None,
        "summary": summary,
        "sourceName": "东方财富研报中心",
        "sourcePageUrl": f"https://data.eastmoney.com/report/stock.jshtml?stockcode={company['ticker']}",
        "originalPdfUrl": pdf_url,
        "localPdfUrl": local_url,
        "fileSizeBytes": file_size,
        "archivedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    config = read_json(CONFIG_PATH, {})
    previous = read_json(INDEX_PATH, {"reports": []})
    companies = [
        company
        for raw in config.get("listedCompanies", [])
        if isinstance(raw, dict) and (company := normalize_company(raw))
    ]
    previous_reports = {
        report.get("id"): report
        for report in previous.get("reports", [])
        if isinstance(report, dict) and report.get("id")
    }
    collected: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []

    for company in companies:
        fetched = 0
        archived = 0
        error = ""
        try:
            records = fetch_company_reports(company["ticker"])
            fetched = len(records)
            normalized: list[dict[str, Any]] = []
            for record in records:
                if not isinstance(record, dict):
                    continue
                try:
                    report = build_report(record, company)
                except Exception as report_error:  # keep scanning other public PDFs
                    log(f"{company['ticker']} skipped report: {report_error}")
                    continue
                if report:
                    normalized.append(report)
                if len(normalized) >= MAX_REPORTS_PER_COMPANY:
                    break
            collected.extend(normalized)
            archived = len(normalized)
        except Exception as company_error:
            error = str(company_error)
            log(f"{company['ticker']} failed: {error}")
            retained = [
                report
                for report in previous_reports.values()
                if report.get("companySlug") == company["slug"]
            ][:MAX_REPORTS_PER_COMPANY]
            collected.extend(retained)
            archived = len(retained)
        statuses.append(
            {
                "source": f"东方财富 · {company['name']} {company['ticker']}",
                "status": "ok" if not error else "partial",
                "fetched": fetched,
                "archived": archived,
                **({"error": error[:300]} if error else {}),
            }
        )

    unique = {report["id"]: report for report in collected if report.get("id")}
    reports = sorted(unique.values(), key=lambda report: report.get("publishedAt", ""), reverse=True)
    reports = reports[:MAX_TOTAL_REPORTS]
    referenced = {Path(report["localPdfUrl"]).name for report in reports if report.get("localPdfUrl")}
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    for path in PDF_DIR.glob("eastmoney-*.pdf"):
        if path.name not in referenced:
            path.unlink()

    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "reports": reports,
        "sourceStatus": statuses,
    }
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    log(f"archived {len(reports)} validated PDF report(s) from {len(companies)} tracked A-share companies")
    return 0 if reports or not companies else 1


if __name__ == "__main__":
    raise SystemExit(main())
