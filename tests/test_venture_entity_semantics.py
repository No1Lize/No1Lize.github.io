from __future__ import annotations

import copy
import unittest

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer


CATALOG = '''
export const companies = [
  { slug:"anthropic", name:"Anthropic", englishName:"Anthropic", region:"US", sector:"AI", stage:"Growth", status:"未上市", summary:"Anthropic builds reliable AI systems.", product:"Claude 模型、Claude Platform", source:official("Anthropic","https://www.anthropic.com/") },
  { slug:"aurora", name:"Aurora Innovation", englishName:"Aurora Innovation", region:"US", sector:"自动驾驶", stage:"上市", status:"已上市", summary:"Aurora develops autonomous trucking technology.", product:"Aurora Driver", source:official("Aurora","https://aurora.tech/") },
];
export type Institution = {};
export const institutionCatalog = [
  { slug:"fund", name:"Example Capital", englishName:"Example Capital", region:"US", type:"VC", stages:"Seed", sectors:["AI"], source:official("Example Capital","https://example.vc/") },
];
export type IpoCompany = {};
'''


class VentureEntitySemanticTests(unittest.TestCase):
    def test_rejects_third_party_financing_and_year_product(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic is an AI safety and research company.",
                    "technology": (
                        "OpenAI models attacked another platform. "
                        "Anthropic builds reliable and steerable AI systems."
                    ),
                    "products": ["Claude 模型", "Claude Platform", "2025"],
                    "team": [],
                    "financing": [
                        {
                            "date": "2026-07-20",
                            "title": "Infinity raises $15M from OpenAI and Anthropic researchers",
                            "summary": "Infinity announced a funding round involving Anthropic researchers.",
                            "sourceUrl": "https://example.com/infinity-round",
                        }
                    ],
                    "capitalMarkets": [],
                    "technologyProducts": [
                        {
                            "name": "Claude 模型",
                            "description": "OpenAI models attacked another platform.",
                            "technicalHighlights": ["OpenAI models attacked another platform."],
                            "sourceUrl": "",
                        },
                        {
                            "name": "2025",
                            "description": "A year label.",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        },
                    ],
                    "projectBackground": {
                        "summary": "Anthropic is an AI safety company.",
                        "problemSolved": "Ninety-Nine Prolog Problems are exercises.",
                        "marketOpportunity": "Anthropic serves enterprise AI users.",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        profile = cleaned["companies"]["anthropic"]
        self.assertEqual(profile["products"], ["Claude 模型", "Claude Platform"])
        self.assertEqual(profile["financing"], [])
        self.assertNotIn("OpenAI models attacked", profile["technology"])
        self.assertIn("Anthropic builds reliable", profile["technology"])
        self.assertEqual(profile["projectBackground"]["problemSolved"], "")
        self.assertEqual(len(profile["technologyProducts"]), 1)
        self.assertIn("公开资料将Claude 模型列为", profile["technologyProducts"][0]["description"])
        self.assertEqual(profile["technologyProducts"][0]["technicalHighlights"], [])
        self.assertEqual(diagnostics["removedFinancing"], 1)
        self.assertEqual(diagnostics["removedProducts"], 1)

    def test_trims_investor_relations_page_chrome(self) -> None:
        payload = {
            "companies": {
                "aurora": {
                    "slug": "aurora",
                    "name": "Aurora Innovation",
                    "background": (
                        "Aurora Innovation develops autonomous trucking technology. "
                        "1654 Smallman Street Toll-Free: 888-000-0000 Investor Relations "
                        "Transfer Agent Featured News."
                    ),
                    "technology": "Aurora Driver supports autonomous trucking.",
                    "products": ["Aurora Driver"],
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
        background = cleaned["companies"]["aurora"]["background"]
        self.assertIn("autonomous trucking technology", background)
        self.assertNotIn("Toll-Free", background)
        self.assertNotIn("Investor Relations", background)

    def test_catalog_fallback_and_research_technology_filter(self) -> None:
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
                    "projectBackground": {
                        "summary": "Stale summary.",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
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
        self.assertEqual(profile["projectBackground"]["summary"], profile["background"])

    def test_capital_summary_matches_structural_finalizer(self) -> None:
        events = [
            {
                "date": "2026-07-20",
                "title": "Anthropic raises a new round",
                "amount": "$2 billion",
                "round": "Growth",
                "investors": ["Example Capital"],
            }
        ]
        self.assertEqual(
            semantics._capital_summary(events),
            finalizer._capital_summary(events),
        )
        self.assertEqual(
            semantics._capital_summary([]),
            finalizer._capital_summary([]),
        )

    def test_keeps_entity_subject_financing(self) -> None:
        row = {
            "title": "Anthropic raises $2 billion in new funding",
            "summary": "Anthropic announced the financing round.",
            "sourceUrl": "https://news.example.com/anthropic-round",
        }
        self.assertTrue(
            semantics._subject_evidence(
                row,
                ("Anthropic",),
                "anthropic.com",
                semantics.FINANCING_ACTION_RE,
            )
        )

    def test_complex_snapshot_reaches_fixed_point_in_one_call(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems. Investor Relations Transfer Agent.",
                    "technology": "OpenAI models are discussed. Anthropic develops Claude models.",
                    "products": ["Claude 模型", "2025"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [
                        {
                            "name": "Claude 模型",
                            "description": "Unrelated OpenAI product description.",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        }
                    ],
                    "projectBackground": {
                        "summary": "Stale derived summary.",
                        "problemSolved": "Unrelated exercise collection.",
                        "marketOpportunity": "Anthropic serves enterprise AI users.",
                    },
                    "capitalSummary": {
                        "eventCount": 9,
                        "summary": "Stale capital summary.",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        first, diagnostics = semantics.enforce_snapshot(copy.deepcopy(payload), CATALOG)
        second, second_diagnostics = semantics.enforce_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(first, second)
        self.assertGreaterEqual(diagnostics["internalPasses"], 2)
        self.assertEqual(second_diagnostics["changedCompanies"], 0)
        self.assertEqual(first["companies"]["anthropic"]["products"], ["Claude 模型"])
        self.assertEqual(first["companies"]["anthropic"]["capitalSummary"]["eventCount"], 0)

    def test_is_idempotent(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude models.",
                    "products": ["Claude 模型"],
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
        first, _ = semantics.enforce_snapshot(copy.deepcopy(payload), CATALOG)
        second, diagnostics = semantics.enforce_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(first, second)
        self.assertEqual(diagnostics["changedCompanies"], 0)
        self.assertTrue(
            second["qualityGate"]["checks"]["entitySemanticConsistency"]["passed"]
        )


if __name__ == "__main__":
    unittest.main()
