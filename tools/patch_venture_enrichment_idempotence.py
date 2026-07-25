#!/usr/bin/env python3
"""Separate official venture evidence from rebuildable research enrichment."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CRAWLER = ROOT / "tools" / "crawl_venture_profiles.py"
ENRICHER = ROOT / "tools" / "enrich_venture_profiles.py"
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
TESTS = ROOT / "tests" / "test_venture_profile_enrichment.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_crawler() -> None:
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
        # Research-layer fields are regenerated after every crawl and must not
        # become the next crawl's canonical evidence. Retain only source-backed
        # identity fields when a site is temporarily unavailable.
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
    replace_once(CRAWLER, old, new, "research-aware retention fields")
    replace_once(
        CRAWLER,
        'merged[field] = previous.get(field)',
        'merged[field] = previous_for_retention.get(field)',
        "research-aware scalar retention",
    )
    replace_once(
        CRAWLER,
        'merged[field] = _merge_lists(merged.get(field), previous.get(field))',
        'merged[field] = _merge_lists(merged.get(field), previous_for_retention.get(field))',
        "research-aware list retention",
    )


def patch_enricher() -> None:
    replace_once(
        ENRICHER,
        "RESEARCH_MODEL_VERSION = 2",
        "RESEARCH_MODEL_VERSION = 3",
        "research model version",
    )

    old_existing = '''    existing = profile.get("projectBackground")
    if isinstance(existing, dict) and clean_text(existing.get("summary"), 760):
        return {
            "summary": clean_text(existing.get("summary"), 760),
            "problemSolved": clean_text(existing.get("problemSolved"), 460),
            "marketOpportunity": clean_text(existing.get("marketOpportunity"), 460),
        }
    aliases = company.aliases
'''
    new_existing = '''    # Always rebuild the research layer from canonical official fields and
    # currently attributed articles. Reusing a previous derived summary would
    # make stale or misattributed text self-perpetuating.
    aliases = company.aliases
'''
    replace_once(ENRICHER, old_existing, new_existing, "project background rebuild")

    old_company = '''        matched = _company_articles(slug, company, articles)
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
    new_company = '''        matched = _company_articles(slug, company, articles)
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
        if not research_technology:
            research_technology = profile.get("technology", "")
        profile["researchTechnology"] = research_technology
'''
    replace_once(ENRICHER, old_company, new_company, "canonical company fields")

    old_evidence = '''    evidence_values = [
        profile.get("technology", ""),
        profile.get("background", ""),
'''
    new_evidence = '''    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
'''
    replace_once(ENRICHER, old_evidence, new_evidence, "research technology evidence")


def patch_finalizer() -> None:
    old = '''        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
'''
    new = '''        profile["background"] = sanitize_narrative(profile.get("background", ""), limit=900)
        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
        profile["researchTechnology"] = sanitize_narrative(
            profile.get("researchTechnology", ""),
            fallback=profile.get("technology", ""),
            limit=900,
        )
'''
    replace_once(FINALIZER, old, new, "research technology finalization")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''        self.assertEqual(
            company["projectBackground"]["summary"],
            "研发并商业化通用人工智能模型与开发者平台。",
        )
'''
    replacement = marker + '''        self.assertNotEqual(company["background"], company["projectBackground"]["summary"])
        self.assertNotIn("首页", company["background"])
        self.assertIn("GPT 模型", company["technology"])
        self.assertIn("ChatGPT", company["researchTechnology"])
'''
    if 'self.assertIn("ChatGPT", company["researchTechnology"])' not in text:
        if marker not in text:
            raise SystemExit("layered enrichment assertion marker not found")
        text = text.replace(marker, replacement, 1)

    test_marker = '''    def test_enrichment_is_idempotent(self) -> None:
'''
    retention_test = '''    def test_rebuild_drops_previous_misattributed_research_layer(self) -> None:
        contaminated = copy.deepcopy(self.snapshot)
        profile = contaminated["companies"]["openai"]
        profile["researchModelVersion"] = 2
        profile["projectBackground"] = {
            "summary": "Infinity raised funding with OpenAI researchers.",
            "problemSolved": "Wrong company evidence.",
            "marketOpportunity": "Wrong company evidence.",
        }
        profile["researchTechnology"] = "Anthropic and Infinity unrelated article."
        result = enrich_snapshot(contaminated, self.articles, CATALOG)
        company = result["companies"]["openai"]
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
        self.assertNotIn("Anthropic", company["researchTechnology"])
        self.assertEqual(company["researchModelVersion"], 3)

'''
    if "def test_rebuild_drops_previous_misattributed_research_layer" not in text:
        if test_marker not in text:
            raise SystemExit("layered enrichment test insertion marker not found")
        text = text.replace(test_marker, retention_test + test_marker, 1)

    TESTS.write_text(text, encoding="utf-8")
    print("layered enrichment regressions: applied")


def main() -> int:
    patch_crawler()
    patch_enricher()
    patch_finalizer()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
