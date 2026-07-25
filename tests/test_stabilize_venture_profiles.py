from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from tools import enforce_venture_entity_semantics as semantics
from tools import finalize_venture_profiles as finalizer
from tools import stabilize_venture_profiles as stabilizer


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
  { slug:"anduril", name:"Anduril Industries", englishName:"Anduril Industries", region:"美国", sector:"智能制造", stage:"成长期", status:"运营中", founded:"2017", headquarters:"California", summary:"开发自主系统、传感器和国防软件平台。", product:"Lattice 平台与多类自主飞行器。", source:official("Anduril","https://www.anduril.com/"), confidence:0.96 },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [];
export type IpoCompany = {};
'''


class VentureProfileStabilizerTests(unittest.TestCase):
    def test_real_gates_share_one_terminal_fixed_point(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T17:44:03+00:00",
            "companies": {
                "anduril": {
                    "slug": "anduril",
                    "name": "Anduril Industries",
                    "updatedAt": "2026-07-25T17:43:00+00:00",
                    "status": "partial",
                    "background": "",
                    "technology": "Lattice 平台与多类自主飞行器。",
                    "researchTechnology": "Anduril Industries develops Lattice autonomous systems.",
                    "products": ["Lattice 平台与多类自主飞行器"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                    "projectBackground": {
                        "summary": "",
                        "problemSolved": "",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }

        stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, CATALOG)
        company = stabilized["companies"]["anduril"]
        structural_check, _ = finalizer.finalize_snapshot(stabilized, CATALOG)
        semantic_check, _ = semantics.enforce_snapshot(stabilized, CATALOG)

        self.assertTrue(diagnostics["converged"])
        self.assertEqual(company["background"], "开发自主系统、传感器和国防软件平台。")
        self.assertEqual(company["products"], ["Lattice 平台", "多类自主飞行器"])
        self.assertEqual(structural_check, stabilized)
        self.assertEqual(semantic_check, stabilized)

    def test_converges_when_gates_need_multiple_passes(self) -> None:
        payload = {"value": 0}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(1, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["value"] = max(2, int(result.get("value", 0)))
            return result, {"changedCompanies": int(result != value)}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            stabilized, diagnostics = stabilizer.stabilize_snapshot(payload, "catalog")

        self.assertEqual(stabilized, {"value": 2})
        self.assertTrue(diagnostics["converged"])
        self.assertGreaterEqual(diagnostics["passes"], 1)

    def test_rejects_a_cross_gate_cycle(self) -> None:
        payload = {"state": "a"}

        def finalize(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "b"
            return result, {}

        def enforce(value, _catalog):
            result = copy.deepcopy(value)
            result["state"] = "a"
            return result, {}

        with patch.object(stabilizer, "finalize_snapshot", side_effect=finalize), patch.object(
            stabilizer, "enforce_snapshot", side_effect=enforce
        ):
            with self.assertRaisesRegex(RuntimeError, "cycle"):
                stabilizer.stabilize_snapshot(payload, "catalog", max_passes=4)

    def test_rejects_non_positive_pass_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            stabilizer.stabilize_snapshot({}, "catalog", max_passes=0)


if __name__ == "__main__":
    unittest.main()
