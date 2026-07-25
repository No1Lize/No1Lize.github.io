#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "crawl_research_reports.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"cannot find {label}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        "from urllib.request import Request, urlopen\n",
        "from urllib.request import Request, urlopen\n\nfrom tools.research_report_adapters import (\n    discover_sec_candidates,\n    discover_web_candidates,\n    load_sec_ticker_map,\n)\n",
        "adapter import",
    )
    text = replace_once(
        text,
        'MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(10 * 1024 * 1024)))\n',
        'MAX_PDF_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_BYTES", str(16 * 1024 * 1024)))\nMAX_ARCHIVE_BYTES = int(os.getenv("RESEARCH_REPORT_MAX_ARCHIVE_BYTES", str(120 * 1024 * 1024)))\n',
        "archive limits",
    )
    old_discovery = '''def discover_public_pdf_candidates(\n    company: dict[str, str], website: str\n) -> list[dict[str, str]]:\n    candidates: list[dict[str, str]] = []\n    seen: set[str] = set()\n    for query in bing_queries(company, website):\n        try:\n            raw = request_bytes(BING_RSS.format(query=quote_plus(query)), timeout=25)\n            items = parse_bing_rss(raw)\n        except Exception as error:\n            log(f"{company['ticker']} search failed: {error}")\n            continue\n        for item in items:\n            url = item["url"]\n            if url in seen or not is_research_candidate(item, company, website):\n                continue\n            seen.add(url)\n            candidates.append(item)\n            if len(candidates) >= MAX_SEARCH_RESULTS:\n                return candidates\n    return candidates\n'''
    new_discovery = '''def discover_public_pdf_candidates(\n    company: dict[str, str], website: str\n) -> list[dict[str, str]]:\n    return discover_web_candidates(\n        company,\n        website,\n        request_bytes,\n        max_results=MAX_SEARCH_RESULTS,\n    )\n'''
    text = replace_once(text, old_discovery, new_discovery, "public discovery")
    text = replace_once(
        text,
        '''def crawl_company(\n    company: dict[str, str],\n    website: str,\n    previous_reports: list[dict[str, Any]],\n) -> tuple[list[dict[str, Any]], dict[str, Any]]:\n''',
        '''def crawl_company(\n    company: dict[str, str],\n    website: str,\n    cik: str,\n    previous_reports: list[dict[str, Any]],\n) -> tuple[list[dict[str, Any]], dict[str, Any]]:\n''',
        "crawl signature",
    )
    marker = '''    if len(new_reports) < MAX_REPORTS_PER_COMPANY:\n        candidates = discover_public_pdf_candidates(company, website)\n'''
    sec_block = '''    if len(new_reports) < MAX_REPORTS_PER_COMPANY and cik:\n        sec_candidates = discover_sec_candidates(company, cik, request_bytes)\n        fetched += len(sec_candidates)\n        for candidate in sec_candidates:\n            try:\n                report = archive_public_report(candidate, company)\n            except Exception as error:\n                errors.append(f"SEC PDF {candidate.get('url', '')}: {error}")\n                continue\n            new_reports.append(report)\n            if len(new_reports) >= MAX_REPORTS_PER_COMPANY:\n                break\n\n    if len(new_reports) < MAX_REPORTS_PER_COMPANY:\n        candidates = discover_public_pdf_candidates(company, website)\n'''
    text = replace_once(text, marker, sec_block, "SEC discovery block")
    text = replace_once(
        text,
        '''        "adapters": ["Eastmoney", "public-web", *( ["company-domain"] if website else [] )],\n''',
        '''        "adapters": [\n            "Eastmoney",\n            *( ["SEC"] if cik else [] ),\n            "public-web",\n            *( ["company-domain"] if website else [] ),\n        ],\n''',
        "adapter status",
    )
    text = replace_once(
        text,
        '''    websites = load_company_websites()\n    companies = [\n''',
        '''    websites = load_company_websites()\n    sec_tickers = load_sec_ticker_map(request_bytes)\n    companies = [\n''',
        "SEC ticker map",
    )
    text = replace_once(
        text,
        '''                websites.get(company["slug"], ""),\n                previous_by_company.get(company["slug"], []),\n''',
        '''                websites.get(company["slug"], ""),\n                sec_tickers.get(company["ticker"], ""),\n                previous_by_company.get(company["slug"], []),\n''',
        "executor CIK",
    )
    text = replace_once(
        text,
        '''    reports = sorted(\n        unique.values(), key=lambda report: report.get("publishedAt", ""), reverse=True\n    )[:MAX_TOTAL_REPORTS]\n''',
        '''    ordered_reports = sorted(\n        unique.values(), key=lambda report: report.get("publishedAt", ""), reverse=True\n    )[:MAX_TOTAL_REPORTS]\n    reports: list[dict[str, Any]] = []\n    archive_bytes = 0\n    for report in ordered_reports:\n        file_size = int(report.get("fileSizeBytes") or 0)\n        if reports and file_size > 0 and archive_bytes + file_size > MAX_ARCHIVE_BYTES:\n            continue\n        reports.append(report)\n        archive_bytes += max(0, file_size)\n''',
        "archive budget",
    )
    text = replace_once(text, '"schemaVersion": 2,', '"schemaVersion": 3,', "schema version")
    text = replace_once(
        text,
        '''        "marketCounts": market_counts,\n        "reports": reports,\n''',
        '''        "marketCounts": market_counts,\n        "archiveBytes": archive_bytes,\n        "reports": reports,\n''',
        "archive metadata",
    )
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
