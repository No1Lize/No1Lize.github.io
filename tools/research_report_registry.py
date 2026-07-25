#!/usr/bin/env python3
"""Load stable company research sources already maintained by the repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RESEARCH_SOURCE_OVERRIDES = {
    "horizon-robotics": "https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&lang=EN&market=SEHK&stockId=1000238030",
    "xtalpi": "https://www1.hkexnews.hk/search/titlesearch.xhtml?category=0&lang=EN&market=SEHK&stockId=1000225298",
    "pony-ai": "https://ir.pony.ai/sec-filings",
    "weride": "https://ir.weride.ai/financials/sec-filings/",
    "rigetti": "https://investors.rigetti.com/sec-filings/",
    "ionq": "https://investors.ionq.com/financials/annual-reports/default.aspx",
    "rocket-lab": "https://investors.rocketlabcorp.com/sec-filings/",
    "tempus-ai": "https://investors.tempus.com/financials/sec-filings/default.aspx",
    "recursion": "https://ir.recursion.com/financials/sec-filings/default.aspx",
    "mobileye": "https://ir.mobileye.com/financials/sec-filings/default.aspx",
    "aurora": "https://ir.aurora.tech/financials/sec-filings/default.aspx",
    "joby": "https://investors.jobyaviation.com/financials/sec-filings/default.aspx",
}

# Verified direct URLs from the corresponding HKEX listed-company title pages.
# These are used only when the dynamic title-search page cannot expose its links
# to the crawler. The original HKEX page remains the sourcePageUrl.
CURATED_PDF_CANDIDATES: dict[str, list[dict[str, str]]] = {
    "horizon-robotics": [
        {
            "title": "Horizon Robotics Annual Report 2025",
            "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0430/2026043001830.pdf",
            "publishedAt": "2026-04-30",
            "description": "HKEX Annual Report 2025 · Horizon Robotics",
        }
    ],
    "xtalpi": [
        {
            "title": "XtalPi Annual Report 2025",
            "url": "https://www1.hkexnews.hk/listedco/listconews/sehk/2026/0417/2026041701551.pdf",
            "publishedAt": "2026-04-17",
            "description": "HKEX Annual Report 2025 · XtalPi Holdings",
        }
    ],
}

STABLE_CIK_FALLBACKS = {
    "PONY": "0001969302",
    "WRD": "0001867729",
    "RGTI": "0001838359",
    "IONQ": "0001824920",
    "RKLB": "0001819994",
    "TEM": "0001717115",
    "RXRX": "0001601830",
    "MBLY": "0001910139",
    "AUR": "0001828108",
    "JOBY": "0001819848",
}


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def load_official_websites(root: Path) -> dict[str, str]:
    """Return listed-company slug -> preferred research/IR URL."""

    payload = _read_json(root / "config" / "official_company_sources.json", {})
    companies = payload.get("companies") if isinstance(payload, dict) else []
    result: dict[str, str] = {}
    for company in companies if isinstance(companies, list) else []:
        if not isinstance(company, dict):
            continue
        slug = str(company.get("slug") or "").strip()
        homepage = str(company.get("homepage") or "").strip()
        news_urls = company.get("newsUrls") if isinstance(company.get("newsUrls"), list) else []
        preferred = next(
            (
                str(url).strip()
                for url in news_urls
                if str(url).startswith(("http://", "https://"))
                and any(token in str(url).casefold() for token in ("investor", "investors", "ir."))
            ),
            "",
        )
        url = preferred or homepage
        if slug and url.startswith(("http://", "https://")):
            result[slug] = url
    result.update(RESEARCH_SOURCE_OVERRIDES)
    return result


def load_curated_pdf_candidates() -> dict[str, list[dict[str, str]]]:
    """Return verified public PDF candidates keyed by listed-company slug."""

    return {
        slug: [dict(candidate) for candidate in candidates]
        for slug, candidates in CURATED_PDF_CANDIDATES.items()
    }


def load_local_cik_map(root: Path) -> dict[str, str]:
    """Return ticker -> zero-padded CIK from snapshots plus stable fallbacks."""

    payload = _read_json(root / "public" / "data" / "articles.json", {})
    facts = payload.get("companyFacts") if isinstance(payload, dict) else {}
    result = dict(STABLE_CIK_FALLBACKS)
    for fact in facts.values() if isinstance(facts, dict) else []:
        if not isinstance(fact, dict):
            continue
        ticker = str(fact.get("ticker") or "").strip().upper()
        cik_raw = "".join(character for character in str(fact.get("cik") or "") if character.isdigit())
        if ticker and cik_raw:
            result[ticker] = cik_raw.zfill(10)
    return result


def merge_source_maps(primary: dict[str, str], fallback: dict[str, str]) -> dict[str, str]:
    """Keep explicit primary values while filling missing keys from fallback."""

    return {**fallback, **{key: value for key, value in primary.items() if value}}
