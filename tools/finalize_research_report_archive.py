#!/usr/bin/env python3
"""Finalize the current all-company PDF archive without a full network recrawl."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import crawl_research_reports as crawler  # noqa: E402
from tools.research_report_registry import load_curated_pdf_candidates  # noqa: E402


def main() -> int:
    config = crawler.read_json(crawler.CONFIG_PATH, {})
    payload = crawler.read_json(crawler.INDEX_PATH, {"reports": [], "sourceStatus": []})
    companies = [
        company
        for raw in config.get("listedCompanies", [])
        if isinstance(raw, dict) and (company := crawler.normalize_company(raw))
    ]
    company_by_slug = {company["slug"]: company for company in companies}

    reports_by_company: dict[str, list[dict]] = {company["slug"]: [] for company in companies}
    for report in payload.get("reports", []):
        if not isinstance(report, dict) or not crawler.report_is_relevant(report):
            continue
        slug = str(report.get("companySlug") or "")
        if slug in reports_by_company:
            reports_by_company[slug].append(report)

    curated = load_curated_pdf_candidates()
    curated_errors: list[str] = []
    for slug, candidates in curated.items():
        company = company_by_slug.get(slug)
        if not company:
            continue
        for candidate in candidates:
            try:
                report = crawler.archive_public_report(candidate, company)
            except Exception as error:
                curated_errors.append(f"{slug}: {error}")
                continue
            reports_by_company[slug].insert(0, report)

    final_reports: list[dict] = []
    for company in companies:
        unique: dict[str, dict] = {}
        for report in reports_by_company[company["slug"]]:
            if not crawler.report_is_relevant(report):
                continue
            report_id = str(report.get("id") or "")
            if report_id and report_id not in unique:
                unique[report_id] = report
        company_reports = sorted(
            unique.values(),
            key=lambda report: report.get("publishedAt", ""),
            reverse=True,
        )[: crawler.MAX_REPORTS_PER_COMPANY]
        final_reports.extend(company_reports)

    final_reports = sorted(
        final_reports,
        key=lambda report: report.get("publishedAt", ""),
        reverse=True,
    )[: crawler.MAX_TOTAL_REPORTS]

    referenced = {
        Path(report["localPdfUrl"]).name
        for report in final_reports
        if report.get("localPdfUrl")
    }
    archive_bytes = 0
    for report in final_reports:
        path = crawler.PDF_DIR / Path(report["localPdfUrl"]).name
        data = path.read_bytes()
        crawler.validate_pdf(data)
        if path.stat().st_size != int(report.get("fileSizeBytes") or 0):
            report["fileSizeBytes"] = path.stat().st_size
        archive_bytes += path.stat().st_size

    for path in crawler.PDF_DIR.glob("*.pdf"):
        if path.name.startswith(("eastmoney-", "public-")) and path.name not in referenced:
            path.unlink()

    existing_status = {
        str(item.get("companySlug") or ""): item
        for item in payload.get("sourceStatus", [])
        if isinstance(item, dict)
    }
    statuses: list[dict] = []
    for company in companies:
        count = sum(
            1 for report in final_reports if report.get("companySlug") == company["slug"]
        )
        status = dict(existing_status.get(company["slug"], {}))
        status.update(
            {
                "source": f"多源公开 PDF · {company['name']} {company['ticker']}",
                "companySlug": company["slug"],
                "market": company["market"],
                "status": "retained" if count else "empty",
                "retained": count,
            }
        )
        adapters = list(status.get("adapters") or [])
        if company["slug"] in curated and "verified-direct" not in adapters:
            adapters.insert(0, "verified-direct")
        status["adapters"] = adapters
        statuses.append(status)

    market_counts = {
        market: sum(1 for company in companies if company["market"] == market)
        for market in ("A股", "港股", "美股")
    }
    report_market_counts = {
        market: sum(1 for report in final_reports if report.get("market") == market)
        for market in ("A股", "港股", "美股")
    }
    if not all(report_market_counts.values()):
        raise RuntimeError(f"missing market PDF coverage: {report_market_counts}")

    output = {
        "schemaVersion": 3,
        "generatedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "trackedCompanies": len(companies),
        "marketCounts": market_counts,
        "archiveBytes": archive_bytes,
        "reports": final_reports,
        "sourceStatus": statuses,
    }
    crawler.INDEX_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "trackedCompanies": len(companies),
                "marketCounts": market_counts,
                "reportMarketCounts": report_market_counts,
                "reports": len(final_reports),
                "archiveBytes": archive_bytes,
                "curatedErrors": curated_errors,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
