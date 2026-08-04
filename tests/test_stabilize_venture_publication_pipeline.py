from __future__ import annotations

import copy
import json
import unittest

from tools.crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, load_snapshot
from tools.ensure_venture_profile_coverage import ensure_catalog_coverage
from tools.enrich_venture_profiles import ARTICLE_PATH, enrich_snapshot
from tools.stabilize_venture_publication_pipeline import stabilize_publication_snapshot
from tools.venture_profile_extraction import parse_catalog


class VenturePublicationFixedPointTests(unittest.TestCase):
    def test_cross_gate_rewrites_converge_to_one_shared_state(self) -> None:
        def evidence(snapshot, _articles, _catalog, *, max_passes=8):
            result = copy.deepcopy(snapshot)
            result["evidence"] = result["terminal"]
            return result, {"maxPasses": max_passes}

        def normalize(snapshot, _catalog):
            result = copy.deepcopy(snapshot)
            result["normalized"] = min(int(result["evidence"]) + 1, 2)
            return result, {"normalized": 1}

        def terminal(snapshot, _catalog, *, max_passes=8):
            result = copy.deepcopy(snapshot)
            result["terminal"] = result["normalized"]
            return result, {"maxPasses": max_passes}

        stabilized, diagnostics = stabilize_publication_snapshot(
            {"evidence": 0, "normalized": 0, "terminal": 0},
            {},
            "",
            evidence_stabilizer=evidence,
            normalizer=normalize,
            terminal_stabilizer=terminal,
        )

        self.assertEqual(
            stabilized,
            {"evidence": 2, "normalized": 2, "terminal": 2},
        )
        self.assertTrue(diagnostics["converged"])
        self.assertEqual(diagnostics["passes"], 3)
        self.assertTrue(diagnostics["history"][-1]["evidenceStable"])
        self.assertTrue(diagnostics["history"][-1]["normalizationStable"])
        self.assertTrue(diagnostics["history"][-1]["terminalStable"])

    def test_cross_gate_cycle_is_rejected(self) -> None:
        def identity_evidence(snapshot, _articles, _catalog, *, max_passes=8):
            return copy.deepcopy(snapshot), {"maxPasses": max_passes}

        def toggle(snapshot, _catalog):
            result = copy.deepcopy(snapshot)
            result["flag"] = not bool(result["flag"])
            return result, {"toggled": 1}

        def identity_terminal(snapshot, _catalog, *, max_passes=8):
            return copy.deepcopy(snapshot), {"maxPasses": max_passes}

        with self.assertRaisesRegex(RuntimeError, "entered a cycle"):
            stabilize_publication_snapshot(
                {"flag": False},
                {},
                "",
                evidence_stabilizer=identity_evidence,
                normalizer=toggle,
                terminal_stabilizer=identity_terminal,
            )

    def test_production_snapshot_reaches_all_publication_gates_together(self) -> None:
        catalog_text = CATALOG_PATH.read_text(encoding="utf-8")
        companies, institutions = parse_catalog(catalog_text)
        snapshot = load_snapshot(OUTPUT_PATH)
        company_profiles, institution_profiles, statuses, quality, _ = (
            ensure_catalog_coverage(
                snapshot,
                companies,
                institutions,
                updated_at="2026-08-04T10:40:00+00:00",
            )
        )
        covered = dict(snapshot)
        covered["schemaVersion"] = max(int(snapshot.get("schemaVersion", 1) or 1), 1)
        covered["generatedAt"] = snapshot.get("generatedAt") or "2026-08-04T10:40:00+00:00"
        covered["companies"] = company_profiles
        covered["institutions"] = institution_profiles
        covered["sourceStatus"] = statuses
        covered["qualityGate"] = quality

        articles = json.loads(ARTICLE_PATH.read_text(encoding="utf-8"))
        enriched = enrich_snapshot(copy.deepcopy(covered), articles, catalog_text)
        stabilized, diagnostics = stabilize_publication_snapshot(
            enriched,
            articles,
            catalog_text,
        )
        checked, check_diagnostics = stabilize_publication_snapshot(
            stabilized,
            articles,
            catalog_text,
        )

        self.assertEqual(stabilized, checked)
        self.assertTrue(diagnostics["converged"])
        self.assertTrue(check_diagnostics["converged"])
        self.assertEqual(check_diagnostics["changedPasses"], 0)
        self.assertEqual(len(stabilized["companies"]), len(companies))
        self.assertEqual(len(stabilized["institutions"]), len(institutions))
        self.assertEqual(len(stabilized["sourceStatus"]), len(companies) + len(institutions))
        self.assertTrue(stabilized["qualityGate"]["passed"])


if __name__ == "__main__":
    unittest.main()
