from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from tools.refine_venture_research_evidence import refine_snapshot
from tools.stabilize_venture_research_evidence import stabilize_evidence_snapshot


ROOT = Path(__file__).resolve().parents[1]


class VentureEvidenceFixedPointTests(unittest.TestCase):
    def test_driver_repeats_until_the_transform_is_a_noop(self) -> None:
        def refiner(snapshot, _articles, _catalog):
            result = copy.deepcopy(snapshot)
            if result["stage"] < 2:
                result["stage"] += 1
            return result, {"advanced": int(result != snapshot)}

        stabilized, diagnostics = stabilize_evidence_snapshot(
            {"stage": 0},
            {},
            "",
            max_passes=5,
            refiner=refiner,
        )
        self.assertEqual(stabilized, {"stage": 2})
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(diagnostics["passes"], 3)
        self.assertEqual(diagnostics["changedPasses"], 2)
        self.assertEqual(diagnostics["totals"]["advanced"], 2)

    def test_driver_rejects_cycles(self) -> None:
        def refiner(snapshot, _articles, _catalog):
            return {"state": 1 - snapshot["state"]}, {"changed": 1}

        with self.assertRaisesRegex(RuntimeError, "cycle"):
            stabilize_evidence_snapshot(
                {"state": 0},
                {},
                "",
                max_passes=5,
                refiner=refiner,
            )

    def test_production_snapshot_reaches_an_actual_refinement_noop(self) -> None:
        snapshot = json.loads(
            (ROOT / "public" / "data" / "venture_profiles.json").read_text(
                encoding="utf-8"
            )
        )
        articles = json.loads(
            (ROOT / "public" / "data" / "articles.json").read_text(encoding="utf-8")
        )
        catalog = (ROOT / "lib" / "catalog-data.ts").read_text(encoding="utf-8")

        stabilized, diagnostics = stabilize_evidence_snapshot(
            snapshot,
            articles,
            catalog,
            max_passes=8,
        )
        checked, _ = refine_snapshot(copy.deepcopy(stabilized), articles, catalog)

        self.assertEqual(checked, stabilized)
        self.assertTrue(diagnostics["converged"])
        self.assertLessEqual(diagnostics["passes"], 8)


if __name__ == "__main__":
    unittest.main()
