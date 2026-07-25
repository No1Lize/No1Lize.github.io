from __future__ import annotations

import copy
import unittest

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer
from tools import stabilize_venture_profiles as stabilizer


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
  { slug:"anthropic", name:"Anthropic", englishName:"Anthropic", region:"US", sector:"AI", stage:"Growth", status:"未上市", summary:"Anthropic builds reliable AI systems.", product:"Claude 模型、Claude Platform", source:official("Anthropic","https://www.anthropic.com/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [];
export type IpoCompany = {};
'''


class VentureProfileStabilizerTests(unittest.TestCase):
    def test_reaches_snapshot_stable_under_both_terminal_gates(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "",
                    "technology": "Claude 模型与 Claude Platform。",
                    "researchTechnology": (
                        "A generic world-model paragraph. "
                        "Anthropic expands Claude Platform for enterprise agents."
                    ),
                    "products": ["Claude 模型", "Claude Platform", "2025"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [],
                    "projectBackground": {
                        "summary": "Stale summary.",
                        "problemSolved": "Unrelated exercise collection.",
                        "marketOpportunity": "",
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

        stable, diagnostics = stabilizer.stabilize_snapshot(
            copy.deepcopy(payload), CATALOG
        )
        structurally_final, _ = finalizer.finalize_snapshot(
            copy.deepcopy(stable), CATALOG
        )
        semantically_final, semantic_diagnostics = semantics.enforce_snapshot(
            copy.deepcopy(stable), CATALOG
        )

        self.assertEqual(stable, structurally_final)
        self.assertEqual(stable, semantically_final)
        self.assertTrue(diagnostics["passed"])
        self.assertGreaterEqual(diagnostics["cycles"], 2)
        self.assertEqual(semantic_diagnostics["changedCompanies"], 0)
        profile = stable["companies"]["anthropic"]
        self.assertEqual(profile["background"], "Anthropic builds reliable AI systems.")
        self.assertEqual(profile["products"], ["Claude 模型", "Claude Platform"])
        self.assertNotIn("generic world-model", profile["researchTechnology"].casefold())
        self.assertEqual(profile["capitalSummary"]["eventCount"], 0)

    def test_is_idempotent(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {},
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        first, _ = stabilizer.stabilize_snapshot(copy.deepcopy(payload), CATALOG)
        second, diagnostics = stabilizer.stabilize_snapshot(
            copy.deepcopy(first), CATALOG
        )
        self.assertEqual(first, second)
        self.assertEqual(diagnostics["cycles"], 1)


if __name__ == "__main__":
    unittest.main()
