#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "crawl_research_reports.py"

DIRECT_IMPORT = '''from tools.research_report_adapters import (
    discover_sec_candidates,
    discover_web_candidates,
    load_sec_ticker_map,
)
'''

FALLBACK_IMPORT = '''try:
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
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"cannot find {label}")
    return text.replace(old, new, 1)


def normalize_adapter_import(text: str) -> str:
    duplicate = f"{DIRECT_IMPORT}\n{FALLBACK_IMPORT}"
    if duplicate in text:
        return text.replace(duplicate, FALLBACK_IMPORT, 1)
    if FALLBACK_IMPORT in text:
        return text
    if DIRECT_IMPORT in text:
        return text.replace(DIRECT_IMPORT, FALLBACK_IMPORT, 1)
    raise RuntimeError("cannot find research report adapter import")


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = normalize_adapter_import(text)
    text = replace_once(
        text,
        'MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(10 * 1024 * 1024)))\n',
        'MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(16 * 1024 * 1024)))\nMAX_ARCHIVE_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_ARCHIVE_BYTES", str(120 * 1024 * 1024)))\n',
        "archive limits",
    )
    old_discovery = '''def discover_public_pdf_candidates(
    company: dict[str, str], website: str
) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    seen: set[str] = set()
    for query in bing_queries(company, website):
        try:
            raw = request_bytes(BING_RSS.format(query=quote_plus(query)), timeout=25)
            items = parse_bing_rss(raw)
        except Exception as error:
            log(f"{company['ticker']} search failed: {error}")
            continue
        for item in items:
            url = item["url"]
            if url in seen or not is_research_candidate(item, company, website):
                continue
            seen.add(url)
            candidates.append(item)
            if len(candidates) >= MAX_SEARCH_RESULTS:
                return candidates
    return candidates
'''
    new_discovery = '''def discover_public_pdf_candidates(
    company: dict[str, str], website: str
) -> list[dict[str, str]]:
    return discover_web_candidates(
        company,
        website,
        request_bytes,
        max_results=MAX_SEARCH_RESULTS,
    )
'''
    text = replace_once(text, old_discovery, new_discovery, "public discovery")
    text = replace_once(
        text,
        '''def crawl_company(
    company: dict[str, str],
    website: str,
    previous_reports: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
''',
        '''def crawl_company(
    company: dict[str, str],
    website: str,
    cik: str,
    previous_reports: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
''',
        "crawl signature",
    )
    marker = '''    if len(new_reports) < MAX_REPORTS_PER_COMPANY:
        candidates = discover_public_pdf_candidates(company, website)
'''
    sec_block = '''    if len(new_reports) < MAX_REPORTS_PER_COMPANY and cik:
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
'''
    text = replace_once(text, marker, sec_block, "SEC discovery block")
    text = replace_once(
        text,
        '''        "adapters": ["Eastmoney", "public-web", *( ["company-domain"] if website else [] )],
''',
        '''        "adapters": [
            "Eastmoney",
            *( ["SEC"] if cik else [] ),
            "public-web",
            *( ["company-domain"] if website else [] ),
        ],
''',
        "adapter status",
    )
    text = replace_once(
        text,
        '''    websites = load_company_websites()
    companies = [
''',
        '''    websites = load_company_websites()
    sec_tickers = load_sec_ticker_map(request_bytes)
    companies = [
''',
        "SEC ticker map",
    )
    text = replace_once(
        text,
        '''                websites.get(company["slug"], ""),
                previous_by_company.get(company["slug"], []),
''',
        '''                websites.get(company["slug"], ""),
                sec_tickers.get(company["ticker"], ""),
                previous_by_company.get(company["slug"], []),
''',
        "executor CIK",
    )
    text = replace_once(
        text,
        '''    reports = sorted(
        unique.values(), key=lambda report: report.get("publishedAt", ""), reverse=True
    )[:MAX_TOTAL_REPORTS]
''',
        '''    ordered_reports = sorted(
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
''',
        "archive budget",
    )
    text = replace_once(text, '"schemaVersion": 2,', '"schemaVersion": 3,', "schema version")
    text = replace_once(
        text,
        '''        "marketCounts": market_counts,
        "reports": reports,
''',
        '''        "marketCounts": market_counts,
        "archiveBytes": archive_bytes,
        "reports": reports,
''',
        "archive metadata",
    )
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
