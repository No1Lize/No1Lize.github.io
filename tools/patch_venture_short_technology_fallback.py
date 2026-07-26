#!/usr/bin/env python3
"""Preserve short technology summaries and rebuild noisy technology prose."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_stabilize_venture_profiles.py"
ENTITY_TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        FINALIZER,
        '''        profile["technology"] = sanitize_narrative(profile.get("technology", ""), limit=900)
        profile["researchTechnology"] = sanitize_narrative(
''',
        '''        raw_technology = clean_text(profile.get("technology", ""), 900)
        profile["technology"] = sanitize_narrative(raw_technology, limit=900)
        if (
            not profile["technology"]
            and raw_technology.startswith("核心技术与产品包括")
        ):
            profile["technology"] = raw_technology
        profile["researchTechnology"] = sanitize_narrative(
''',
        "structural short technology fallback",
    )
    replace_once(
        SEMANTICS,
        '''        technology = _relevant_clauses(
            profile.get("technology", ""), aliases, products, limit=900
        )
        if not technology and products:
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        '''        raw_technology = clean_text(profile.get("technology", ""), 1400)
        technology = _relevant_clauses(
            raw_technology, aliases, products, limit=900
        )
        if products and (
            not technology
            or PRODUCT_EDITORIAL_RE.search(raw_technology)
            or PRODUCT_URL_RE.search(raw_technology)
        ):
            technology = f"核心技术与产品包括{'、'.join(products[:8])}。"
''',
        "noisy technology reconstruction",
    )

    marker = '''    def test_converges_when_gates_need_multiple_passes(self) -> None:
'''
    addition = '''    def test_short_generated_technology_is_a_shared_fixed_point(self) -> None:
        catalog = """
        export type Company = {};
        export const companies: Company[] = [
          { slug:"form-energy", name:"Form Energy", englishName:"Form Energy", region:"美国", sector:"新能源", stage:"成长期", status:"运营中", founded:"2017", headquarters:"Massachusetts", summary:"开发多日储能系统。", product:"多日储能系统", source:official("Form Energy","https://formenergy.com/"), confidence:0.96 },
        ];
        export type Institution = {};
        export const institutionCatalog: Institution[] = [];
        export type IpoCompany = {};
        """
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T17:44:03+00:00",
            "companies": {
                "form-energy": {
                    "slug": "form-energy",
                    "name": "Form Energy",
                    "background": "开发多日储能系统。",
                    "technology": "核心技术与产品包括多日储能系统。",
                    "researchTechnology": "核心技术与产品包括多日储能系统。",
                    "products": ["多日储能系统"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                    "projectBackground": {
                        "summary": "开发多日储能系统。",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, catalog)
        company = stabilized["companies"]["form-energy"]
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(company["technology"], "核心技术与产品包括多日储能系统。")
        self.assertEqual(company["researchTechnology"], company["technology"])
        structural_check, _ = finalizer.finalize_snapshot(stabilized, catalog)
        semantic_check, _ = semantics.enforce_snapshot(stabilized, catalog)
        self.assertEqual(structural_check, stabilized)
        self.assertEqual(semantic_check, stabilized)

'''
    text = TESTS.read_text(encoding="utf-8")
    if "def test_short_generated_technology_is_a_shared_fixed_point" not in text:
        if marker not in text:
            raise SystemExit("short technology test insertion point not found")
        TESTS.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")
        print("short technology regression: applied")
    else:
        print("short technology regression: already applied")

    replace_once(
        ENTITY_TESTS,
        '''                    "technology": "Anthropic develops Claude Platform.",
''',
        '''                    "technology": "核心技术与产品包括Claude Platform、https:、www.example.com、英特尔深化智能生态合作。",
''',
        "noisy technology regression fixture",
    )
    replace_once(
        ENTITY_TESTS,
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
''',
        '''        self.assertEqual(
            cleaned["companies"]["anthropic"]["products"],
            ["Claude Platform"],
        )
        self.assertEqual(
            cleaned["companies"]["anthropic"]["technology"],
            "核心技术与产品包括Claude Platform。",
        )
''',
        "clean technology regression assertion",
    )


if __name__ == "__main__":
    main()
