from __future__ import annotations

import copy
import json
import unittest

from tools import enforce_venture_entity_semantics as entity_semantics
from tools import finalize_venture_profiles as structural_finalization
from tools import normalize_venture_profiles as base_normalization
from tools import refine_venture_research_evidence as research_evidence
from tools.crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH, load_snapshot
from tools.ensure_venture_profile_coverage import ensure_catalog_coverage
from tools.enrich_venture_profiles import ARTICLE_PATH, enrich_snapshot
from tools.stabilize_venture_publication_pipeline import (
    align_capital_event_patterns,
    stabilize_publication_snapshot,
)
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

    def test_public_company_merger_uses_one_cross_gate_classification(self) -> None:
        align_capital_event_patterns()
        title = (
            "In Major Step Toward Commercializing Self-Driving Technology, "
            "Aurora to Become a Public Company by Merging with Reinvent Technology Partners Y"
        )
        article = {
            "publishedAt": "2026-08-04",
            "title": title,
            "summary": (
                "Aurora announced a business combination that will take the company public."
            ),
            "source": {
                "url": (
                    "https://aurora.tech/newsroom/"
                    "in-major-step-toward-commercializing-self-driving-technology"
                )
            },
        }

        self.assertIsNotNone(research_evidence.CAPITAL_MARKET_RE.search(title))
        self.assertIsNotNone(base_normalization.CAPITAL_MARKET_ACTION_PATTERN.search(title))
        self.assertIsNotNone(structural_finalization.CAPITAL_EVIDENCE_RE.search(title))
        self.assertIsNotNone(entity_semantics.CAPITAL_ACTION_RE.search(title))

        financing, capital = research_evidence._route_capital_events({}, [article])
        self.assertEqual(financing, [])
        self.assertEqual(len(capital), 1)
        retained_by_normalization = base_normalization.normalize_capital_events(
            capital, capital_market=True
        )
        self.assertEqual(retained_by_normalization, capital)
        retained_by_structure = structural_finalization.finalize_capital_markets(capital)
        self.assertEqual(retained_by_structure, capital)
        retained_by_terminal = entity_semantics._sanitize_events(
            capital,
            ("Aurora",),
            "aurora.tech",
            entity_semantics.CAPITAL_ACTION_RE,
        )
        self.assertEqual(retained_by_terminal, capital)

    def test_context_without_transaction_action_is_not_a_capital_event(self) -> None:
        align_capital_event_patterns()
        false_positives = (
            "ByteDance restructures AI business, merging Doubao and Feishu product teams",
            "IonQ (NYSE: IONQ) will release its Q2 2026 financial results after market close",
            "Recursion (Nasdaq: RXRX) to participate in upcoming investor conferences",
            "Aurora (Nasdaq: AUR) is delivering the benefits of self-driving technology",
        )
        for text in false_positives:
            with self.subTest(text=text):
                self.assertIsNone(research_evidence.CAPITAL_MARKET_RE.search(text))
                self.assertIsNone(
                    base_normalization.CAPITAL_MARKET_ACTION_PATTERN.search(text)
                )
                self.assertIsNone(structural_finalization.CAPITAL_EVIDENCE_RE.search(text))
                self.assertIsNone(entity_semantics.CAPITAL_ACTION_RE.search(text))

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
