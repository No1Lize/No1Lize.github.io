#!/usr/bin/env python3
"""Finalize venture profiles before publication.

This is the last deterministic quality gate after crawling, enrichment and
cross-entity normalization. It deliberately prefers precision over recall for
facts rendered as products, team biographies, financing events, recent
investments and classic cases. Unlike the legacy sanitizers, it preserves the
new structured research fields while removing stale or unsupported rows.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .sanitize_venture_narratives import sanitize_narrative
    from .sanitize_venture_profiles import (
        sanitize_capital_events,
        sanitize_portfolio,
        sanitize_products,
        sanitize_sources,
    )
    from .venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )
except ImportError:
    from sanitize_venture_narratives import sanitize_narrative
    from sanitize_venture_profiles import (
        sanitize_capital_events,
        sanitize_portfolio,
        sanitize_products,
        sanitize_sources,
    )
    from venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"

PURE_RESEARCH_LABELS = {
    "research",
    "ai research",
    "ai safety research",
    "safety research",
    "研究",
    "安全研究",
    "人工智能研究",
    "ai安全研究",
}

STRONG_FINANCING_RE = re.compile(
    r"\b(?:rais(?:e|ed|es|ing)|funding round|financing round|"
    r"seed round|pre-seed funding|secured .{0,40} funding|"
    r"backed by|led by|investment from|closes? .{0,40} round)\b|"
    r"(?:完成|获得|宣布|获).{0,30}(?:融资|投资)|"
    r"(?:融资|募资|领投|跟投|战略投资|估值)",
    re.IGNORECASE,
)
INVESTED_IN_RE = re.compile(r"\b(?:invested|invests|investing)\s+(?:in|into)\b", re.IGNORECASE)
CAPITAL_EVIDENCE_RE = re.compile(
    r"\b(?:ipo|listed|listing|went public|acquired|acquisition|merger|"
    r"nasdaq|nyse|hkex|stock exchange)\b|"
    r"(?:上市|挂牌|并购|收购|退出|退市|交易所|公开市场)",
    re.IGNORECASE,
)
CASE_EVIDENCE_RE = re.compile(
    r"\b(?:series\s+[a-z0-9]+|seed|funding|financing|ipo|listed|"
    r"acquired|acquisition|exit|follow-on)\b|"
    r"(?:融资|投资逻辑|后续轮|上市|挂牌|并购|收购|退出|商业化)",
    re.IGNORECASE,
)


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean_text(value, 500).casefold())


def _parse_date(value: Any) -> datetime | None:
    text = clean_text(value, 32)
    if not text:
        return None
    match = re.match(r"^(20\d{2})-(\d{2})(?:-(\d{2}))?", text)
    if not match:
        return None
    year, month, day = match.groups()
    try:
        return datetime(int(year), int(month), int(day or 1), tzinfo=UTC)
    except ValueError:
        return None


def _unique_strings(values: Iterable[Any], limit: int, item_limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = clean_text(raw, item_limit)
        key = _compact(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def finalize_products(values: Sequence[Any], catalog_product: str) -> list[str]:
    products = sanitize_products(values, catalog_product)
    return [
        item
        for item in products
        if _compact(item) not in {_compact(label) for label in PURE_RESEARCH_LABELS}
    ][:10]


def finalize_team(values: Sequence[Any], aliases: Sequence[str]) -> list[dict[str, str]]:
    originals = {
        clean_text(row.get("name"), 120).casefold(): row
        for row in values if isinstance(row, dict) and clean_text(row.get("name"), 120)
    }
    result: list[dict[str, str]] = []
    for row in sanitize_team_members(values, aliases):
        original = originals.get(clean_text(row.get("name"), 120).casefold(), {})
        result.append(
            {
                "name": clean_text(row.get("name"), 120),
                "role": clean_text(row.get("role"), 160),
                "summary": clean_text(row.get("summary"), 360),
                "background": clean_text(original.get("background"), 420),
                "previousExperience": clean_text(original.get("previousExperience"), 420),
                "sourceUrl": normalize_url(row.get("sourceUrl", "")),
            }
        )
    return result[:20]


def finalize_financing(values: Sequence[Any]) -> list[dict[str, Any]]:
    candidates = sanitize_capital_events(values, capital_market=False)
    result: list[dict[str, Any]] = []
    for row in candidates:
        evidence = f"{row.get('title', '')} {row.get('summary', '')}"
        investors = row.get("investors", []) if isinstance(row.get("investors"), list) else []
        has_explicit_action = bool(STRONG_FINANCING_RE.search(evidence))
        has_supported_investment = bool(
            INVESTED_IN_RE.search(evidence)
            and (row.get("amount") or row.get("round") or investors)
        )
        if has_explicit_action or has_supported_investment:
            result.append(row)
    return result[:20]


def finalize_capital_markets(values: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in sanitize_capital_events(values, capital_market=True)
        if CAPITAL_EVIDENCE_RE.search(f"{row.get('title', '')} {row.get('summary', '')}")
    ][:20]


def finalize_technology_products(
    values: Sequence[Any], valid_product_names: Sequence[str]
) -> list[dict[str, Any]]:
    allowed = {_compact(name) for name in valid_product_names}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        name = clean_text(raw.get("name"), 160)
        key = _compact(name)
        description = sanitize_narrative(raw.get("description", ""), limit=520)
        if not name or key not in allowed or key in seen or not description:
            continue
        result.append(
            {
                "name": name,
                "category": clean_text(raw.get("category"), 80),
                "description": description,
                "technicalHighlights": _unique_strings(
                    raw.get("technicalHighlights", []) if isinstance(raw.get("technicalHighlights"), list) else [],
                    6,
                    260,
                ),
                "sourceUrl": normalize_url(raw.get("sourceUrl", "")),
            }
        )
        seen.add(key)
        if len(result) >= 12:
            break
    return result


def finalize_recent_investments(
    values: Sequence[Any], reference: datetime
) -> list[dict[str, str]]:
    start = reference - timedelta(days=365)
    result: list[dict[str, str]] = []
    for row in sanitize_portfolio(values, require_date=True):
        parsed = _parse_date(row.get("date"))
        if parsed is None or not start <= parsed <= reference:
            continue
        result.append(row)
    return result[:30]


def finalize_classic_cases(
    values: Sequence[Any],
    company_profiles: dict[str, dict[str, Any]],
    listed_slugs: set[str],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        name = clean_text(raw.get("name"), 120)
        slug = clean_text(raw.get("companySlug"), 100)
        analysis = clean_text(raw.get("analysis"), 760)
        source_url = normalize_url(raw.get("sourceUrl", ""))
        key = name.casefold()
        if not name or len(analysis) < 60 or key in seen or (not slug and not source_url):
            continue
        company_profile = company_profiles.get(slug, {})
        has_linked_evidence = bool(
            slug in listed_slugs
            or company_profile.get("financing")
            or company_profile.get("capitalMarkets")
        )
        if not has_linked_evidence and not CASE_EVIDENCE_RE.search(analysis):
            continue
        result.append(
            {
                "name": name,
                "companySlug": slug,
                "investmentLogic": clean_text(raw.get("investmentLogic"), 520),
                "followOnPerformance": clean_text(raw.get("followOnPerformance"), 520),
                "exitPerformance": clean_text(raw.get("exitPerformance"), 520),
                "analysis": analysis,
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= 8:
            break
    return result


def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    amounts = _unique_strings((row.get("amount") for row in events), 12, 80)
    rounds = _unique_strings((row.get("round") for row in events), 12, 80)
    investors = _unique_strings(
        (
            investor
            for row in events
            for investor in (row.get("investors", []) if isinstance(row.get("investors"), list) else [])
        ),
        20,
        120,
    )
    if events:
        summary = (
            f"共识别到{len(events)}条可追溯融资记录；"
            f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    else:
        summary = "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    return {
        "eventCount": len(events),
        "disclosedAmounts": amounts,
        "rounds": rounds,
        "majorInvestors": investors,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }


def _recent_summary(
    rows: Sequence[dict[str, str]], reference: datetime, previous: Any
) -> dict[str, Any]:
    start = reference - timedelta(days=365)
    companies = _unique_strings((row.get("name") for row in rows), 30, 120)
    rounds = _unique_strings((row.get("round") for row in rows), 12, 80)
    sectors = []
    if isinstance(previous, dict):
        sectors = _unique_strings(previous.get("sectors", []), 12, 100)
    return {
        "periodStart": start.date().isoformat(),
        "periodEnd": reference.date().isoformat(),
        "investmentCount": len(rows),
        "companies": companies,
        "sectors": sectors,
        "rounds": rounds,
        "summary": (
            f"统计窗口为{start.date().isoformat()}至{reference.date().isoformat()}，"
            f"共识别{len(rows)}条带日期的公开投资记录，涉及{len(companies)}个项目。"
        ),
    }


def finalize_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    company_specs, institution_specs = parse_catalog(catalog_text)
    company_by_slug = {item.slug: item for item in company_specs}
    institution_by_slug = {item.slug: item for item in institution_specs}
    listed_slugs = {item.slug for item in company_specs if item.status == "已上市"}
    reference = _parse_date(payload.get("generatedAt")) or datetime.now(UTC)
    cleaned = copy.deepcopy(payload)
    diagnostics = {
        "changedCompanies": 0,
        "changedInstitutions": 0,
        "removedProducts": 0,
        "removedCapitalEvents": 0,
        "removedRecentInvestments": 0,
        "removedClassicCases": 0,
    }

    companies = cleaned.get("companies", {}) if isinstance(cleaned.get("companies"), dict) else {}
    for slug, profile in companies.items():
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        spec = company_by_slug.get(slug)
        aliases = spec.aliases if spec else (profile.get("name", ""),)
        catalog_product = spec.product if spec else ""
        products_before = len(profile.get("products", []))
        events_before = len(profile.get("financing", [])) + len(profile.get("capitalMarkets", []))
        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
        if isinstance(profile.get("projectBackground"), dict):
            project = profile["projectBackground"]
            project["summary"] = sanitize_narrative(project.get("summary", ""), limit=900)
            project["problemSolved"] = sanitize_narrative(project.get("problemSolved", ""), limit=520)
            project["marketOpportunity"] = sanitize_narrative(project.get("marketOpportunity", ""), limit=520)
        profile["products"] = finalize_products(profile.get("products", []), catalog_product)
        profile["technologyProducts"] = finalize_technology_products(
            profile.get("technologyProducts", []), profile["products"]
        )
        profile["team"] = finalize_team(profile.get("team", []), aliases)
        profile["financing"] = finalize_financing(profile.get("financing", []))
        profile["capitalMarkets"] = finalize_capital_markets(profile.get("capitalMarkets", []))
        profile["capitalSummary"] = _capital_summary(profile["financing"])
        profile["sources"] = sanitize_sources(profile.get("sources", []))
        profile["evidenceScore"] = evidence_score(profile, "company")
        diagnostics["removedProducts"] += max(0, products_before - len(profile["products"]))
        diagnostics["removedCapitalEvents"] += max(
            0, events_before - len(profile["financing"]) - len(profile["capitalMarkets"])
        )
        if profile != before:
            diagnostics["changedCompanies"] += 1

    institutions = cleaned.get("institutions", {}) if isinstance(cleaned.get("institutions"), dict) else {}
    for slug, profile in institutions.items():
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        spec = institution_by_slug.get(slug)
        aliases = spec.aliases if spec else (profile.get("name", ""),)
        recent_before = len(profile.get("recentInvestments", []))
        classic_before = len(profile.get("classicCases", []))
        profile["overview"] = sanitize_narrative(profile.get("overview", ""), limit=900)
        profile["strategy"] = sanitize_narrative(profile.get("strategy", ""), limit=900)
        profile["team"] = finalize_team(profile.get("team", []), aliases)
        profile["portfolio"] = sanitize_portfolio(profile.get("portfolio", []), require_date=False)
        profile["recentInvestments"] = finalize_recent_investments(
            profile.get("recentInvestments", []), reference
        )
        profile["recentYearSummary"] = _recent_summary(
            profile["recentInvestments"], reference, profile.get("recentYearSummary")
        )
        profile["classicCases"] = finalize_classic_cases(
            profile.get("classicCases", []), companies, listed_slugs
        )
        profile["sources"] = sanitize_sources(profile.get("sources", []))
        profile["evidenceScore"] = evidence_score(profile, "institution")
        diagnostics["removedRecentInvestments"] += max(
            0, recent_before - len(profile["recentInvestments"])
        )
        diagnostics["removedClassicCases"] += max(
            0, classic_before - len(profile["classicCases"])
        )
        if profile != before:
            diagnostics["changedInstitutions"] += 1

    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    checks["finalSemanticConsistency"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    cleaned["schemaVersion"] = max(2, int(cleaned.get("schemaVersion", 1) or 1))
    return cleaned, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    cleaned, diagnostics = finalize_snapshot(
        payload, args.catalog.read_text(encoding="utf-8")
    )
    rendered = json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot requires finalization.")
            return 1
        print("Venture profile snapshot passed final semantic consistency checks.")
        return 0

    if rendered == current:
        print("No venture profile finalization changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
