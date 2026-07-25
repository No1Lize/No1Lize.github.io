#!/usr/bin/env python3
"""Migrate venture profiles to canonical and rebuildable evidence layers.

Executed once by the owner-only venture PR runner. The migration patches the
production pipeline, adds regressions, removes stale derived contamination from
the committed snapshot, and is deleted after all publication gates pass.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from urllib.parse import urlsplit


ROOT = Path(__file__).resolve().parents[1]
CRAWLER = ROOT / "tools" / "crawl_venture_profiles.py"
ENRICHER = ROOT / "tools" / "enrich_venture_profiles.py"
REFINER = ROOT / "tools" / "refine_venture_research_evidence.py"
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
TS_MODEL = ROOT / "lib" / "venture-profile-data.ts"
COMPANY_PAGE = ROOT / "app" / "companies" / "[slug]" / "page.tsx"
ENRICH_TESTS = ROOT / "tests" / "test_venture_profile_enrichment.py"
REFINE_TESTS = ROOT / "tests" / "test_refine_venture_research_evidence.py"
SNAPSHOT = ROOT / "public" / "data" / "venture_profiles.json"
CATALOG = ROOT / "lib" / "catalog-data.ts"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def insert_before(path: Path, marker: str, block: str, sentinel: str) -> None:
    text = path.read_text(encoding="utf-8")
    if sentinel in text:
        print(f"{sentinel}: already applied")
        return
    index = text.find(marker)
    if index < 0:
        raise SystemExit(f"{sentinel}: insertion marker not found in {path}")
    path.write_text(text[:index] + block.rstrip() + "\n\n" + text[index:], encoding="utf-8")
    print(f"{sentinel}: inserted")


def replace_function(path: Path, name: str, next_name: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    if block.rstrip() in text:
        print(f"{name}: already applied")
        return
    start = text.find(f"def {name}(")
    end = text.find(f"\n\ndef {next_name}(", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{name}: function boundary not found in {path}")
    path.write_text(text[:start] + block.rstrip() + text[end:], encoding="utf-8")
    print(f"{name}: replaced")


def patch_imports_and_version() -> None:
    text = ENRICHER.read_text(encoding="utf-8")
    if "from .sanitize_venture_narratives import sanitize_narrative" not in text:
        text = text.replace(
            "try:\n    from .venture_profile_extraction import (",
            "try:\n    from .sanitize_venture_narratives import sanitize_narrative\n    from .venture_profile_extraction import (",
            1,
        )
        text = text.replace(
            "except ImportError:\n    from venture_profile_extraction import (",
            "except ImportError:\n    from sanitize_venture_narratives import sanitize_narrative\n    from venture_profile_extraction import (",
            1,
        )
    text = text.replace("RESEARCH_MODEL_VERSION = 2", "RESEARCH_MODEL_VERSION = 3", 1)
    ENRICHER.write_text(text, encoding="utf-8")
    print("enricher imports and model version: applied")


def strict_article_helpers() -> tuple[str, str, str]:
    helper = '''def _entity_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\\u3400-\\u9fff]+",
        "",
        clean_text(value, 160).casefold(),
    )'''
    company = '''def _company_articles(
    slug: str,
    company: CatalogCompany,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in company.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        article_slug = clean_text(article.get("companySlug"), 100)
        company_name = clean_text(article.get("company"), 120)
        if article_slug:
            if article_slug == slug:
                result.append(article)
            continue
        if company_name and _entity_key(company_name) in alias_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    institution = '''def _institution_articles(
    institution: CatalogInstitution,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in institution.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        named_keys = {
            _entity_key(item)
            for item in _article_institutions(article)
            if _entity_key(item)
        }
        if alias_keys & named_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    return helper, company, institution


def patch_enricher() -> None:
    patch_imports_and_version()
    helper, company_block, institution_block = strict_article_helpers()
    insert_before(ENRICHER, "def _company_articles(", helper, "def _entity_key(")
    replace_function(ENRICHER, "_company_articles", "_institution_articles", company_block)
    replace_function(ENRICHER, "_institution_articles", "_capital_event_from_article", institution_block)

    project_block = '''def _company_project_background(
    company: CatalogCompany,
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
) -> dict[str, str]:
    aliases = company.aliases
    article_values = [
        f"{article.get('title', '')}。{article.get('summary', '')}"
        for article in articles[:20]
    ]
    raw_background = profile.get("background", "")
    summary = _select_sentences(
        [raw_background, *article_values],
        aliases,
        (
            "founded", "mission", "company", "成立", "使命", "致力于", "总部", "研发",
        ),
        maximum=3,
        limit=760,
    )
    if not summary or _navigation_heavy(raw_background):
        summary = sanitize_narrative(company.summary, limit=760) or clean_text(company.summary, 760)
    problem = _select_sentences(
        [raw_background, profile.get("technology", ""), *article_values],
        aliases,
        PROBLEM_TERMS,
        maximum=2,
        limit=460,
    )
    market = _select_sentences(
        [raw_background, profile.get("technology", ""), *article_values],
        aliases,
        MARKET_TERMS,
        maximum=2,
        limit=460,
    )
    return {
        "summary": summary or clean_text(company.summary, 760),
        "problemSolved": problem,
        "marketOpportunity": market,
    }'''
    replace_function(ENRICHER, "_company_project_background", "_capital_summary", project_block)

    replace_once(
        ENRICHER,
        '''    evidence_values = [
        profile.get("technology", ""),
        profile.get("background", ""),
''',
        '''    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
''',
        "research technology product evidence",
    )

    old_company_layer = '''        matched = _company_articles(slug, company, articles)
        profile = raw_profile
        project = _company_project_background(company, profile, matched)
        profile["background"] = project["summary"]
        profile["projectBackground"] = project
        technology = _select_sentences(
            [
                profile.get("technology", ""),
                *(
                    f"{item.get('title', '')}。{item.get('summary', '')}"
                    for item in matched[:20]
                ),
            ],
            company.aliases,
            TECH_HIGHLIGHT_TERMS,
            maximum=3,
            limit=760,
        )
        if not technology or _navigation_heavy(profile.get("technology", "")):
            technology = clean_text(company.product, 760) or technology
        profile["technology"] = technology
'''
    new_company_layer = '''        matched = _company_articles(slug, company, articles)
        profile = raw_profile
        profile["background"] = sanitize_narrative(
            profile.get("background", ""),
            fallback=company.summary,
            limit=900,
        )
        profile["technology"] = sanitize_narrative(
            profile.get("technology", ""),
            fallback=company.product,
            limit=900,
        )
        project = _company_project_background(company, profile, matched)
        profile["projectBackground"] = project
        research_technology = _select_sentences(
            [
                profile.get("technology", ""),
                *(
                    f"{item.get('title', '')}。{item.get('summary', '')}"
                    for item in matched[:20]
                ),
            ],
            company.aliases,
            TECH_HIGHLIGHT_TERMS,
            maximum=3,
            limit=760,
        )
        profile["researchTechnology"] = research_technology or profile.get("technology", "")
'''
    replace_once(ENRICHER, old_company_layer, new_company_layer, "canonical and research company layers")


def patch_refiner() -> None:
    helper = '''def _entity_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\\u3400-\\u9fff]+",
        "",
        clean_text(value, 160).casefold(),
    )'''
    insert_before(REFINER, "def _company_articles(", helper, "def _entity_key(")

    company_block = '''def _company_articles(
    company: CatalogCompany, articles: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in company.aliases if _entity_key(item)}
    matched: list[dict[str, Any]] = []
    for article in articles:
        article_slug = clean_text(article.get("companySlug"), 100)
        company_name = clean_text(article.get("company"), 120)
        if article_slug:
            if article_slug == company.slug:
                matched.append(article)
            continue
        if company_name and _entity_key(company_name) in alias_keys:
            matched.append(article)
    return sorted(
        matched,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    replace_function(REFINER, "_company_articles", "_institution_articles", company_block)

    institution_block = '''def _institution_articles(
    institution: CatalogInstitution, articles: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in institution.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        named_keys = {
            _entity_key(item)
            for item in _article_institutions(article)
            if _entity_key(item)
        }
        if alias_keys & named_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )'''
    replace_function(REFINER, "_institution_articles", "_select_required_sentence", institution_block)

    project_block = '''def _clean_project_background(
    company: CatalogCompany,
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
) -> dict[str, str]:
    catalog_summary = (
        sanitize_narrative(company.summary, limit=760)
        or clean_text(company.summary, 760)
    )
    official_summary = _select_required_sentence(
        (profile.get("background", ""),),
        required_aliases=company.aliases,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=760,
    )
    summary = official_summary or catalog_summary or "当前公开来源未提供可核对的项目背景说明。"
    non_capital_articles = [
        _article_text(article)
        for article in articles[:30]
        if not CAPITAL_MARKET_RE.search(_article_text(article))
        and not FINANCING_RE.search(_article_text(article))
        and clean_text(article.get("type"), 60)
        not in {"融资", "产业投资", "IPO", "并购", "监管文件"}
    ]
    evidence = [
        profile.get("background", ""),
        profile.get("technology", ""),
        profile.get("researchTechnology", ""),
        *non_capital_articles,
    ]
    problem = _select_required_sentence(
        evidence,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        evidence,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    return {
        "summary": summary,
        "problemSolved": problem,
        "marketOpportunity": market,
    }'''
    replace_function(REFINER, "_clean_project_background", "_product_aliases", project_block)
    replace_once(
        REFINER,
        '''    evidence_values = [
        profile.get("technology", ""),
        profile.get("background", ""),
''',
        '''    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
''',
        "refiner research technology evidence",
    )


def patch_crawler_retention() -> None:
    old = '''    merged = copy.deepcopy(current)
    if kind == "company":
        scalar_fields = ("background", "technology")
        list_fields = ("products", "team", "financing", "capitalMarkets", "sources")
    else:
        scalar_fields = ("overview", "strategy")
        list_fields = ("team", "recentInvestments", "portfolio", "classicCases", "sources")
'''
    new = '''    merged = copy.deepcopy(current)
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
'''
    replace_once(CRAWLER, old, new, "research-aware crawler retention")
    replace_once(
        CRAWLER,
        "merged[field] = previous.get(field)",
        "merged[field] = previous_for_retention.get(field)",
        "research-aware scalar source",
    )
    replace_once(
        CRAWLER,
        "merged[field] = _merge_lists(merged.get(field), previous.get(field))",
        "merged[field] = _merge_lists(merged.get(field), previous_for_retention.get(field))",
        "research-aware list source",
    )


def patch_finalizer_and_frontend() -> None:
    replace_once(
        FINALIZER,
        '''        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
''',
        '''        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
        profile["researchTechnology"] = sanitize_narrative(
            profile.get("researchTechnology", ""),
            fallback=profile.get("technology", ""),
            limit=900,
        )
''',
        "research technology finalization",
    )
    replace_once(
        TS_MODEL,
        "  technology: string;\n  products: string[];",
        "  technology: string;\n  researchTechnology?: string;\n  products: string[];",
        "research technology type",
    )
    replace_once(
        TS_MODEL,
        "    technology: sanitizeVentureNarrative(raw.technology, 900),\n    products:",
        "    technology: sanitizeVentureNarrative(raw.technology, 900),\n    researchTechnology: sanitizeVentureNarrative(raw.researchTechnology, 900) || undefined,\n    products:",
        "research technology normalization",
    )
    replace_once(
        TS_MODEL,
        "    background: projectBackground?.summary || fallbackBackground,",
        "    background: fallbackBackground,",
        "canonical background normalization",
    )
    replace_once(
        COMPANY_PAGE,
        "  const technology = venture?.technology || research.technology;",
        "  const technology = venture?.researchTechnology || venture?.technology || research.technology;",
        "research technology rendering",
    )


def add_regressions() -> None:
    text = ENRICH_TESTS.read_text(encoding="utf-8")
    fixture_marker = '''                {
                    "id": "openai-product",
'''
    false_fixture = '''                {
                    "id": "infinity-funding",
                    "company": "Infinity",
                    "companySlug": "infinity",
                    "title": "Infinity raises a new round",
                    "summary": "Infinity raised funding with researchers from OpenAI and Anthropic; a Sequoia Capital observer commented on the market.",
                    "type": "融资",
                    "sector": "AI / AGI",
                    "publishedAt": "2026-07-20",
                    "institutions": ["Touring Capital"],
                    "source": {"url": "https://example.com/infinity-funding"},
                },
'''
    if '"id": "infinity-funding"' not in text:
        if fixture_marker not in text:
            raise SystemExit("enrichment fixture marker not found")
        text = text.replace(fixture_marker, false_fixture + fixture_marker, 1)
    assertion_marker = '        self.assertEqual(company["capitalSummary"]["eventCount"], 1)\n'
    assertions = '''        self.assertEqual(company["capitalSummary"]["eventCount"], 1)
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
        self.assertNotIn("Anthropic", company["researchTechnology"])
        self.assertEqual(company["researchModelVersion"], 3)
'''
    if 'self.assertNotIn("Infinity", company["projectBackground"]["summary"])' not in text:
        if assertion_marker not in text:
            raise SystemExit("enrichment assertion marker not found")
        text = text.replace(assertion_marker, assertions, 1)
    ENRICH_TESTS.write_text(text, encoding="utf-8")

    text = REFINE_TESTS.read_text(encoding="utf-8")
    refine_fixture_marker = '''                {
                    "company": "智元机器人",
                    "companySlug": "agibot",
                    "title": "远征A3技术说明",
'''
    unrelated = '''                {
                    "company": "Infinity",
                    "companySlug": "infinity",
                    "title": "Infinity完成融资",
                    "summary": "Infinity完成融资，研究人员曾来自智元机器人，Sequoia Capital未参与本轮。",
                    "type": "融资",
                    "publishedAt": "2026-07-20",
                    "institutions": ["Touring Capital"],
                    "source": {"url": "https://example.com/infinity"},
                },
'''
    if '"companySlug": "infinity"' not in text:
        if refine_fixture_marker not in text:
            raise SystemExit("refiner fixture marker not found")
        text = text.replace(refine_fixture_marker, unrelated + refine_fixture_marker, 1)
    refine_assertion = '        self.assertEqual(len(company["financing"]), 1)\n'
    refine_assertions = '''        self.assertEqual(len(company["financing"]), 1)
        self.assertNotIn("Infinity", company["financing"][0]["title"])
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
'''
    if 'self.assertNotIn("Infinity", company["financing"][0]["title"])' not in text:
        if refine_assertion not in text:
            raise SystemExit("refiner assertion marker not found")
        text = text.replace(refine_assertion, refine_assertions, 1)
    REFINE_TESTS.write_text(text, encoding="utf-8")
    print("strict attribution regressions: applied")


def domain(value: str) -> str:
    host = (urlsplit(value).hostname or "").casefold().removeprefix("www.")
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def reset_snapshot() -> None:
    from venture_profile_extraction import clean_text, parse_catalog

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    companies, institutions = parse_catalog(CATALOG.read_text(encoding="utf-8"))
    company_map = {item.slug: item for item in companies}
    institution_map = {item.slug: item for item in institutions}

    for slug, profile in payload.get("companies", {}).items():
        if not isinstance(profile, dict):
            continue
        spec = company_map.get(slug)
        if spec is None:
            continue
        official_domain = domain(spec.source_url)
        profile["background"] = clean_text(spec.summary, 900)
        profile["technology"] = clean_text(spec.product, 900)
        for field in (
            "projectBackground", "researchTechnology", "technologyProducts",
            "capitalSummary", "exitPerformance",
        ):
            profile.pop(field, None)
        for event_field in ("financing", "capitalMarkets"):
            profile[event_field] = [
                row
                for row in profile.get(event_field, [])
                if isinstance(row, dict)
                and official_domain
                and domain(clean_text(row.get("sourceUrl"), 1000)) == official_domain
            ]
        cleaned_team = []
        for row in profile.get("team", []):
            if not isinstance(row, dict):
                continue
            cleaned_team.append(
                {
                    "name": clean_text(row.get("name"), 120),
                    "role": clean_text(row.get("role"), 160),
                    "summary": "",
                    "background": "",
                    "previousExperience": "",
                    "sourceUrl": clean_text(row.get("sourceUrl"), 1000),
                }
            )
        profile["team"] = cleaned_team
        profile["researchModelVersion"] = 0

    for slug, profile in payload.get("institutions", {}).items():
        if not isinstance(profile, dict):
            continue
        spec = institution_map.get(slug)
        if spec is None:
            continue
        official_domain = domain(spec.source_url)
        for field in ("recentInvestments", "portfolio"):
            profile[field] = [
                row
                for row in profile.get(field, [])
                if isinstance(row, dict)
                and official_domain
                and domain(clean_text(row.get("sourceUrl"), 1000)) == official_domain
            ]
        profile["classicCases"] = []
        profile.pop("recentYearSummary", None)
        profile["researchModelVersion"] = 0

    payload["researchModelVersion"] = 3
    SNAPSHOT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("contaminated derived snapshot fields: reset")


def main() -> None:
    patch_enricher()
    patch_refiner()
    patch_crawler_retention()
    patch_finalizer_and_frontend()
    add_regressions()
    reset_snapshot()


if __name__ == "__main__":
    main()
