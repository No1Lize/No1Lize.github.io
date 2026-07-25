#!/usr/bin/env python3
"""Build evidence-backed startup and investment institution profiles.

The crawler reads the production catalog, discovers a bounded set of official
pages for every entity and writes ``public/data/venture_profiles.json``.
Failures are isolated per entity and a richer previous profile is retained when
an official website becomes unavailable or temporarily loses content.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from .venture_profile_extraction import (
        BACKGROUND_KEYWORDS,
        CAPITAL_MARKET_KEYWORDS,
        FINANCING_KEYWORDS,
        INSTITUTION_OVERVIEW_KEYWORDS,
        INSTITUTION_STRATEGY_KEYWORDS,
        PRODUCT_KEYWORDS,
        TECHNOLOGY_KEYWORDS,
        CatalogCompany,
        CatalogInstitution,
        ParsedPage,
        accepted_section_count,
        classify_page,
        clean_text,
        common_path_candidates,
        evidence_score,
        extract_capital_events,
        extract_institution_portfolio,
        extract_products,
        extract_team,
        sanitize_product_items,
        sanitize_team_members,
        normalize_url,
        parse_catalog,
        parse_public_page,
        score_discovered_links,
        select_summary,
        source_record,
    )
except ImportError:
    from venture_profile_extraction import (
        BACKGROUND_KEYWORDS,
        CAPITAL_MARKET_KEYWORDS,
        FINANCING_KEYWORDS,
        INSTITUTION_OVERVIEW_KEYWORDS,
        INSTITUTION_STRATEGY_KEYWORDS,
        PRODUCT_KEYWORDS,
        TECHNOLOGY_KEYWORDS,
        CatalogCompany,
        CatalogInstitution,
        ParsedPage,
        accepted_section_count,
        classify_page,
        clean_text,
        common_path_candidates,
        evidence_score,
        extract_capital_events,
        extract_institution_portfolio,
        extract_products,
        extract_team,
        sanitize_product_items,
        sanitize_team_members,
        normalize_url,
        parse_catalog,
        parse_public_page,
        score_discovered_links,
        select_summary,
        source_record,
    )


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
OUTPUT_PATH = ROOT / "public" / "data" / "venture_profiles.json"
DEFAULT_USER_AGENT = (
    "LizeRoadOne/4.0 contact=No1Lize@users.noreply.github.com "
    "(+https://github.com/No1Lize/No1Lize.github.io)"
)
REQUEST_TIMEOUT = 12
REQUEST_ATTEMPTS = 2
MAX_RESPONSE_BYTES = 4_000_000


class FetchError(RuntimeError):
    pass


def decode_body(raw: bytes, content_type: str) -> str:
    charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.IGNORECASE)
    candidates = [charset_match.group(1)] if charset_match else []
    head = raw[:4096].decode("ascii", errors="ignore")
    meta_match = re.search(r"charset=[\"']?([A-Za-z0-9._-]+)", head, re.IGNORECASE)
    if meta_match:
        candidates.append(meta_match.group(1))
    candidates.extend(("utf-8", "gb18030", "big5", "latin-1"))
    for charset in candidates:
        try:
            return raw.decode(charset)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_text(
    url: str,
    user_agent: str,
    *,
    timeout: int = REQUEST_TIMEOUT,
    attempts: int = REQUEST_ATTEMPTS,
) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.6",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Cache-Control": "no-cache",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise FetchError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
                return decode_body(raw, response.headers.get("Content-Type", ""))
        except (HTTPError, URLError, TimeoutError, OSError, FetchError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.5 * (attempt + 1))
    raise FetchError(f"{type(last_error).__name__}: {last_error}")


def load_snapshot(path: Path = OUTPUT_PATH) -> dict[str, Any]:
    if not path.exists():
        return {
            "schemaVersion": 1,
            "generatedAt": "",
            "companies": {},
            "institutions": {},
            "sourceStatus": [],
            "qualityGate": {},
        }
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "schemaVersion": 1,
            "generatedAt": "",
            "companies": {},
            "institutions": {},
            "sourceStatus": [],
            "qualityGate": {},
        }
    return payload if isinstance(payload, dict) else {}


def _pages_for(pages: Sequence[ParsedPage], sections: Sequence[str]) -> list[ParsedPage]:
    selected = [page for page in pages if any(section in page.sections for section in sections)]
    return selected or list(pages)


def _candidate_urls(home: ParsedPage, homepage: str, kind: str, max_pages: int) -> list[str]:
    result: list[str] = []
    seen = {normalize_url(homepage)}
    for _, url in score_discovered_links(home, homepage, kind):
        if url in seen:
            continue
        result.append(url)
        seen.add(url)
        if len(result) >= max_pages - 1:
            return result
    for url in common_path_candidates(homepage, kind):
        if not url or url in seen:
            continue
        result.append(url)
        seen.add(url)
        if len(result) >= max_pages - 1:
            break
    return result


def crawl_pages(
    homepage: str,
    kind: str,
    user_agent: str,
    max_pages: int,
    fetcher: Callable[[str, str], str] = fetch_text,
) -> tuple[list[ParsedPage], list[str]]:
    pages: list[ParsedPage] = []
    warnings: list[str] = []
    normalized_home = normalize_url(homepage)
    if not normalized_home:
        return pages, ["invalid official homepage"]

    try:
        home_body = fetcher(normalized_home, user_agent)
        home = parse_public_page(normalized_home, home_body, kind)
        pages.append(home)
    except Exception as exc:
        return pages, [f"homepage {type(exc).__name__}: {exc}"]

    for url in _candidate_urls(pages[0], normalized_home, kind, max(1, max_pages)):
        try:
            body = fetcher(url, user_agent)
            page = parse_public_page(url, body, kind)
            if len(page.text) < 80 and not page.people:
                warnings.append(f"thin page: {url}")
                continue
            pages.append(page)
        except Exception as exc:
            warnings.append(f"{url}: {type(exc).__name__}: {exc}")
    return pages, warnings


def _company_capital_fallback(company: CatalogCompany) -> list[dict[str, Any]]:
    if company.status != "已上市":
        return []
    return [
        {
            "date": "",
            "type": "上市",
            "title": f"{company.name}已进入公开市场",
            "summary": f"目录将{company.name}标记为已上市公司；页面继续通过交易所、监管文件和公司公告跟踪上市后的经营与资本市场表现。",
            "amount": "",
            "round": company.stage,
            "investors": [],
            "sourceUrl": company.source_url,
        }
    ]


def build_company_profile(
    company: CatalogCompany,
    pages: Sequence[ParsedPage],
    warnings: Sequence[str],
    updated_at: str,
) -> dict[str, Any]:
    aliases = company.aliases
    background_pages = _pages_for(pages, ("background",))
    technology_pages = _pages_for(pages, ("technology", "products"))
    team_pages = _pages_for(pages, ("team",))
    financing_pages = _pages_for(pages, ("financing",))
    capital_pages = _pages_for(pages, ("capitalMarkets",))

    background = select_summary(
        background_pages,
        BACKGROUND_KEYWORDS,
        aliases,
        company.summary,
        limit=780,
    )
    technology = select_summary(
        technology_pages,
        TECHNOLOGY_KEYWORDS,
        aliases,
        company.product,
        limit=780,
    )
    products = extract_products(technology_pages, company.product)
    team = extract_team(team_pages, aliases)
    financing = extract_capital_events(financing_pages, aliases, capital_market=False)
    capital_markets = extract_capital_events(capital_pages, aliases, capital_market=True)
    if not capital_markets:
        capital_markets = _company_capital_fallback(company)

    sources: list[dict[str, str]] = []
    source_seen: set[str] = set()
    for page in pages:
        section = page.sections[0] if page.sections else "background"
        record = source_record(page, company.source_name, section)
        if record["url"] in source_seen:
            continue
        sources.append(record)
        source_seen.add(record["url"])

    profile: dict[str, Any] = {
        "slug": company.slug,
        "name": company.name,
        "updatedAt": updated_at,
        "status": "fallback",
        "background": background,
        "technology": technology,
        "products": products,
        "team": team,
        "financing": financing,
        "capitalMarkets": capital_markets,
        "sources": sources,
        "warnings": list(warnings)[:12],
    }
    score = evidence_score(profile, "company")
    sections = accepted_section_count(profile, "company")
    if len(pages) >= 2 and sections >= 5:
        profile["status"] = "ok"
    elif pages:
        profile["status"] = "partial"
    profile["evidenceScore"] = score
    return profile


def build_institution_profile(
    institution: CatalogInstitution,
    pages: Sequence[ParsedPage],
    companies: Sequence[CatalogCompany],
    warnings: Sequence[str],
    updated_at: str,
) -> dict[str, Any]:
    aliases = institution.aliases
    overview_pages = _pages_for(pages, ("overview",))
    strategy_pages = _pages_for(pages, ("strategy", "portfolio"))
    team_pages = _pages_for(pages, ("team",))

    overview_fallback = (
        f"{institution.name}是一家位于{institution.region}的{institution.institution_type}，"
        f"公开阶段覆盖{institution.stages}。"
    )
    strategy_fallback = (
        f"公开投资方向覆盖{'、'.join(institution.sectors)}，后续通过新增项目、后续轮融资与退出事件持续检验。"
    )
    overview = select_summary(
        overview_pages,
        INSTITUTION_OVERVIEW_KEYWORDS,
        aliases,
        overview_fallback,
        limit=780,
    )
    strategy = select_summary(
        strategy_pages,
        INSTITUTION_STRATEGY_KEYWORDS,
        aliases,
        strategy_fallback,
        limit=780,
    )
    team = extract_team(team_pages, aliases)
    portfolio, recent, classic = extract_institution_portfolio(pages, companies)

    sources: list[dict[str, str]] = []
    source_seen: set[str] = set()
    for page in pages:
        section = page.sections[0] if page.sections else "overview"
        record = source_record(page, institution.source_name, section)
        if record["url"] in source_seen:
            continue
        sources.append(record)
        source_seen.add(record["url"])

    profile: dict[str, Any] = {
        "slug": institution.slug,
        "name": institution.name,
        "updatedAt": updated_at,
        "status": "fallback",
        "overview": overview,
        "strategy": strategy,
        "team": team,
        "recentInvestments": recent,
        "portfolio": portfolio,
        "classicCases": classic,
        "sources": sources,
        "warnings": list(warnings)[:12],
    }
    score = evidence_score(profile, "institution")
    sections = accepted_section_count(profile, "institution")
    if len(pages) >= 2 and sections >= 4:
        profile["status"] = "ok"
    elif pages:
        profile["status"] = "partial"
    profile["evidenceScore"] = score
    return profile


def _merge_lists(current: Any, previous: Any) -> Any:
    if isinstance(current, list) and current:
        return current
    if isinstance(previous, list):
        return previous
    return current


def retain_richer_profile(
    current: dict[str, Any], previous: dict[str, Any] | None, kind: str
) -> tuple[dict[str, Any], bool]:
    if not previous:
        return current, False
    current_score = int(current.get("evidenceScore", 0) or 0)
    previous_score = int(previous.get("evidenceScore", 0) or 0)
    if current_score >= previous_score and current.get("status") != "fallback":
        return current, False

    merged = copy.deepcopy(current)
    previous_is_enriched = bool(previous.get("researchModelVersion"))
    previous_for_retention = copy.deepcopy(previous)
    if previous_is_enriched:
        retained_team = []
        for item in previous_for_retention.get("team", []):
            if not isinstance(item, dict):
                continue
            retained_team.append(
                {
                    "name": clean_text(item.get("name"), 120),
                    "role": clean_text(item.get("role"), 160),
                    "summary": "",
                    "sourceUrl": normalize_url(item.get("sourceUrl", "")),
                }
            )
        previous_for_retention["team"] = retained_team

    if kind == "company":
        scalar_fields = () if previous_is_enriched else ("background", "technology")
        list_fields = (
            ("products", "team", "sources")
            if previous_is_enriched
            else ("products", "team", "financing", "capitalMarkets", "sources")
        )
    else:
        scalar_fields = ("overview", "strategy")
        list_fields = (
            ("team", "sources")
            if previous_is_enriched
            else ("team", "recentInvestments", "portfolio", "classicCases", "sources")
        )
    for field in scalar_fields:
        if len(clean_text(merged.get(field), 2000)) < len(clean_text(previous.get(field), 2000)):
            merged[field] = previous_for_retention.get(field)
    for field in list_fields:
        merged[field] = _merge_lists(merged.get(field), previous_for_retention.get(field))
    merged["status"] = "retained"
    merged["evidenceScore"] = max(current_score, previous_score)
    merged["warnings"] = [
        *list(current.get("warnings", [])),
        "本轮公开页面信息少于上一版，已保留更完整的历史档案。",
    ][:12]
    return merged, True


def crawl_company(
    company: CatalogCompany,
    user_agent: str,
    max_pages: int,
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    pages, warnings = crawl_pages(company.source_url, "company", user_agent, max_pages)
    updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    profile = build_company_profile(company, pages, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "company")
    # Retained history must pass the latest semantic rules too. Otherwise a
    # temporary homepage outage could resurrect navigation labels from an old
    # snapshot even though new extraction is already stricter.
    profile["team"] = sanitize_team_members(profile.get("team", []), company.aliases)
    profile["products"] = sanitize_product_items(profile.get("products", []))
    profile["evidenceScore"] = evidence_score(profile, "company")
    status = {
        "kind": "company",
        "slug": company.slug,
        "name": company.name,
        "status": profile["status"],
        "fetchedPages": len(pages),
        "acceptedSections": accepted_section_count(profile, "company"),
        "retainedPrevious": retained,
        "elapsedSeconds": round(time.monotonic() - started, 2),
    }
    if warnings:
        status["error"] = "; ".join(warnings[:3])
    return profile, status


def crawl_institution(
    institution: CatalogInstitution,
    companies: Sequence[CatalogCompany],
    user_agent: str,
    max_pages: int,
    previous: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started = time.monotonic()
    pages, warnings = crawl_pages(institution.source_url, "institution", user_agent, max_pages)
    updated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    profile = build_institution_profile(institution, pages, companies, warnings, updated_at)
    profile, retained = retain_richer_profile(profile, previous, "institution")
    profile["team"] = sanitize_team_members(
        profile.get("team", []), institution.aliases
    )
    profile["evidenceScore"] = evidence_score(profile, "institution")
    status = {
        "kind": "institution",
        "slug": institution.slug,
        "name": institution.name,
        "status": profile["status"],
        "fetchedPages": len(pages),
        "acceptedSections": accepted_section_count(profile, "institution"),
        "retainedPrevious": retained,
        "elapsedSeconds": round(time.monotonic() - started, 2),
    }
    if warnings:
        status["error"] = "; ".join(warnings[:3])
    return profile, status


def _invalid_source_urls(profiles: dict[str, dict[str, Any]]) -> list[str]:
    invalid: list[str] = []
    for slug, profile in profiles.items():
        for source in profile.get("sources", []):
            url = normalize_url(source.get("url", ""))
            if not url:
                invalid.append(f"{slug}:{source.get('url', '')}")
    return invalid


def _team_core_rows(values: Sequence[Any]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for raw in values if isinstance(values, list) else []:
        if not isinstance(raw, dict):
            continue
        result.append(
            {
                "name": clean_text(raw.get("name"), 120),
                "role": clean_text(raw.get("role"), 160),
                "summary": clean_text(raw.get("summary"), 320),
                "sourceUrl": normalize_url(raw.get("sourceUrl", "")),
            }
        )
    return result


def evaluate_quality(
    companies: dict[str, dict[str, Any]],
    institutions: dict[str, dict[str, Any]],
    expected_companies: int,
    expected_institutions: int,
    statuses: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    invalid = _invalid_source_urls(companies) + _invalid_source_urls(institutions)
    semantic_errors: list[str] = []
    for slug, profile in companies.items():
        products = profile.get("products", [])
        if products != sanitize_product_items(products):
            semantic_errors.append(f"company:{slug}:product-noise")
        team = profile.get("team", [])
        if _team_core_rows(team) != sanitize_team_members(
            team, (profile.get("name", ""),)
        ):
            semantic_errors.append(f"company:{slug}:team-noise")
    for slug, profile in institutions.items():
        team = profile.get("team", [])
        if _team_core_rows(team) != sanitize_team_members(
            team, (profile.get("name", ""),)
        ):
            semantic_errors.append(f"institution:{slug}:team-noise")
    checks = {
        "companyCoverage": {
            "actual": len(companies),
            "required": expected_companies,
            "passed": len(companies) == expected_companies,
        },
        "institutionCoverage": {
            "actual": len(institutions),
            "required": expected_institutions,
            "passed": len(institutions) == expected_institutions,
        },
        "runtimeStatusCoverage": {
            "actual": len(statuses),
            "required": expected_companies + expected_institutions,
            "passed": len(statuses) == expected_companies + expected_institutions,
        },
        "invalidSourceUrls": {
            "actual": len(invalid),
            "required": 0,
            "passed": not invalid,
        },
        "semanticNoise": {
            "actual": len(semantic_errors),
            "required": 0,
            "passed": not semantic_errors,
        },
    }
    return {
        "passed": all(check["passed"] for check in checks.values()),
        "checks": checks,
        "invalidSourceUrls": invalid[:30],
        "semanticErrors": semantic_errors[:30],
        "productiveCompanies": sum(profile.get("status") in {"ok", "partial", "retained"} for profile in companies.values()),
        "productiveInstitutions": sum(profile.get("status") in {"ok", "partial", "retained"} for profile in institutions.values()),
    }


def write_snapshot(payload: dict[str, Any], previous: dict[str, Any], path: Path = OUTPUT_PATH) -> bool:
    comparable = {key: value for key, value in payload.items() if key != "generatedAt"}
    old_comparable = {key: value for key, value in previous.items() if key != "generatedAt"}
    if comparable == old_comparable and path.exists():
        print("No venture profile snapshot changes.")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"Updated {path.relative_to(ROOT)} "
        f"({len(payload.get('companies', {}))} companies, "
        f"{len(payload.get('institutions', {}))} institutions)."
    )
    return True


def run(
    *,
    kind: str = "all",
    slug: str = "",
    workers: int = 8,
    max_pages: int = 6,
    output_path: Path = OUTPUT_PATH,
) -> tuple[dict[str, Any], int]:
    catalog_text = CATALOG_PATH.read_text(encoding="utf-8")
    company_specs, institution_specs = parse_catalog(catalog_text)
    if not company_specs or not institution_specs:
        raise RuntimeError("catalog parser found no companies or institutions")

    previous = load_snapshot(output_path)
    company_profiles = dict(previous.get("companies", {}))
    institution_profiles = dict(previous.get("institutions", {}))
    previous_status = {
        (str(item.get("kind", "")), str(item.get("slug", ""))): item
        for item in previous.get("sourceStatus", [])
        if isinstance(item, dict)
    }
    statuses: dict[tuple[str, str], dict[str, Any]] = dict(previous_status)
    user_agent = os.environ.get("VENTURE_PROFILE_USER_AGENT", "").strip() or DEFAULT_USER_AGENT

    selected_companies = [
        item for item in company_specs
        if kind in {"all", "company"} and (not slug or item.slug == slug)
    ]
    selected_institutions = [
        item for item in institution_specs
        if kind in {"all", "institution"} and (not slug or item.slug == slug)
    ]
    tasks: list[tuple[str, str, Any]] = []
    for company in selected_companies:
        tasks.append(("company", company.slug, company))
    for institution in selected_institutions:
        tasks.append(("institution", institution.slug, institution))

    with ThreadPoolExecutor(max_workers=max(1, min(12, workers))) as executor:
        future_map = {}
        for task_kind, task_slug, spec in tasks:
            if task_kind == "company":
                future = executor.submit(
                    crawl_company,
                    spec,
                    user_agent,
                    max_pages,
                    company_profiles.get(task_slug),
                )
            else:
                future = executor.submit(
                    crawl_institution,
                    spec,
                    company_specs,
                    user_agent,
                    max_pages,
                    institution_profiles.get(task_slug),
                )
            future_map[future] = (task_kind, task_slug, getattr(spec, "name", task_slug))

        for future in as_completed(future_map):
            task_kind, task_slug, task_name = future_map[future]
            try:
                profile, status = future.result()
            except Exception as exc:
                previous_profile = (
                    company_profiles.get(task_slug)
                    if task_kind == "company"
                    else institution_profiles.get(task_slug)
                )
                if previous_profile:
                    profile = copy.deepcopy(previous_profile)
                    profile["status"] = "retained"
                    profile["warnings"] = [
                        *list(profile.get("warnings", [])),
                        f"本轮抓取异常，保留上一版：{type(exc).__name__}: {exc}",
                    ][:12]
                else:
                    profile = {
                        "slug": task_slug,
                        "name": task_name,
                        "updatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
                        "status": "fallback",
                        "sources": [],
                        "warnings": [f"{type(exc).__name__}: {exc}"],
                        **(
                            {
                                "background": "",
                                "technology": "",
                                "products": [],
                                "team": [],
                                "financing": [],
                                "capitalMarkets": [],
                            }
                            if task_kind == "company"
                            else {
                                "overview": "",
                                "strategy": "",
                                "team": [],
                                "recentInvestments": [],
                                "portfolio": [],
                                "classicCases": [],
                            }
                        ),
                    }
                status = {
                    "kind": task_kind,
                    "slug": task_slug,
                    "name": task_name,
                    "status": profile["status"],
                    "fetchedPages": 0,
                    "acceptedSections": accepted_section_count(profile, task_kind),
                    "retainedPrevious": bool(previous_profile),
                    "error": f"{type(exc).__name__}: {exc}",
                }
            if task_kind == "company":
                company_profiles[task_slug] = profile
            else:
                institution_profiles[task_slug] = profile
            statuses[(task_kind, task_slug)] = status
            print(
                f"{task_kind}={task_slug} status={status['status']} "
                f"pages={status.get('fetchedPages', 0)} sections={status.get('acceptedSections', 0)}",
                file=sys.stderr,
            )

    # A full run guarantees one record and one status for every catalog entity.
    if kind == "all" and not slug:
        for company in company_specs:
            company_profiles.setdefault(
                company.slug,
                build_company_profile(company, [], ["not crawled"], datetime.now(UTC).replace(microsecond=0).isoformat()),
            )
            statuses.setdefault(
                ("company", company.slug),
                {
                    "kind": "company",
                    "slug": company.slug,
                    "name": company.name,
                    "status": company_profiles[company.slug].get("status", "fallback"),
                    "fetchedPages": 0,
                    "acceptedSections": accepted_section_count(company_profiles[company.slug], "company"),
                },
            )
        for institution in institution_specs:
            institution_profiles.setdefault(
                institution.slug,
                build_institution_profile(
                    institution,
                    [],
                    company_specs,
                    ["not crawled"],
                    datetime.now(UTC).replace(microsecond=0).isoformat(),
                ),
            )
            statuses.setdefault(
                ("institution", institution.slug),
                {
                    "kind": "institution",
                    "slug": institution.slug,
                    "name": institution.name,
                    "status": institution_profiles[institution.slug].get("status", "fallback"),
                    "fetchedPages": 0,
                    "acceptedSections": accepted_section_count(institution_profiles[institution.slug], "institution"),
                },
            )

    # Remove profiles and statuses for entities that no longer exist in the
    # production catalog. Partial refreshes may retain current catalog rows,
    # but deleted or renamed entities must not pollute coverage.
    company_keys = {item.slug for item in company_specs}
    institution_keys = {item.slug for item in institution_specs}
    company_profiles = {
        profile_slug: profile
        for profile_slug, profile in company_profiles.items()
        if profile_slug in company_keys
    }
    institution_profiles = {
        profile_slug: profile
        for profile_slug, profile in institution_profiles.items()
        if profile_slug in institution_keys
    }
    statuses = {
        key: status
        for key, status in statuses.items()
        if (key[0] == "company" and key[1] in company_keys)
        or (key[0] == "institution" and key[1] in institution_keys)
    }

    ordered_status = sorted(statuses.values(), key=lambda item: (item.get("kind", ""), item.get("slug", "")))
    quality = evaluate_quality(
        company_profiles,
        institution_profiles,
        len(company_specs),
        len(institution_specs),
        ordered_status,
    )
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "companies": dict(sorted(company_profiles.items())),
        "institutions": dict(sorted(institution_profiles.items())),
        "sourceStatus": ordered_status,
        "qualityGate": quality,
    }
    return payload, 0 if quality["passed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("all", "company", "institution"), default="all")
    parser.add_argument("--slug", default="")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-pages", type=int, default=6)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    if args.validate_only:
        catalog_text = CATALOG_PATH.read_text(encoding="utf-8")
        company_specs, institution_specs = parse_catalog(catalog_text)
        payload = load_snapshot(args.output)
        quality = evaluate_quality(
            payload.get("companies", {}),
            payload.get("institutions", {}),
            len(company_specs),
            len(institution_specs),
            payload.get("sourceStatus", []),
        )
        print(json.dumps(quality, ensure_ascii=False))
        return 0 if quality["passed"] else 1

    payload, exit_code = run(
        kind=args.kind,
        slug=args.slug.strip(),
        workers=args.workers,
        max_pages=max(1, min(10, args.max_pages)),
        output_path=args.output,
    )
    if exit_code == 0:
        write_snapshot(payload, load_snapshot(args.output), args.output)
    else:
        print("Venture profile quality gate failed; previous snapshot retained.", file=sys.stderr)
        print(json.dumps(payload.get("qualityGate", {}), ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
