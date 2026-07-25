#!/usr/bin/env python3
"""Add catalog background fallback and research-technology relevance filtering."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: source block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        SEMANTICS,
        '''        background = _sanitize_background(profile.get("background", ""))
        profile["background"] = background
        technology = _relevant_clauses(
            profile.get("technology", ""), aliases, products, limit=900
        )
        if not technology and products:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
        profile["technology"] = technology
''',
        '''        background = _sanitize_background(profile.get("background", ""))
        if not background and spec:
            background = sanitize_narrative(spec.summary, limit=900)
        profile["background"] = background
        technology = _relevant_clauses(
            profile.get("technology", ""), aliases, products, limit=900
        )
        if not technology and products:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
        profile["technology"] = technology
        research_technology = _relevant_clauses(
            profile.get("researchTechnology", ""), aliases, products, limit=900
        )
        profile["researchTechnology"] = research_technology or technology
''',
        "canonical background fallback and research technology filter",
    )

    tests = TESTS.read_text(encoding="utf-8")
    marker = '''    def test_keeps_entity_subject_financing(self) -> None:
'''
    additions = '''    def test_catalog_fallback_and_research_technology_filter(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "",
                    "technology": "Claude 模型与 Claude Platform。",
                    "researchTechnology": (
                        "Looped world models are a generic research direction. "
                        "Anthropic expands Claude Platform for enterprise agents."
                    ),
                    "products": ["Claude 模型", "Claude Platform"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = semantics.enforce_snapshot(payload, CATALOG)
        profile = cleaned["companies"]["anthropic"]
        self.assertEqual(profile["background"], "Anthropic builds reliable AI systems.")
        self.assertNotIn("Looped world models", profile["researchTechnology"])
        self.assertIn("Anthropic expands Claude Platform", profile["researchTechnology"])
        self.assertEqual(profile["projectBackground"]["summary"], profile["background"] if "projectBackground" in profile else profile["background"])

'''
    if "def test_catalog_fallback_and_research_technology_filter" not in tests:
        if marker not in tests:
            raise SystemExit("entity semantic fallback test insertion point not found")
        TESTS.write_text(tests.replace(marker, additions + marker, 1), encoding="utf-8")

    Path(__file__).unlink()


if __name__ == "__main__":
    main()
