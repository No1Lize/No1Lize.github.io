from __future__ import annotations

import copy
import unittest

from tools.source_health_summary import rebuild_source_health_summary
from tools.tracking_source_governance import normalize_tracking_sources


class SourceHealthSummaryTests(unittest.TestCase):
    def stale_payload(self) -> dict:
        return {
            "schemaVersion": 3,
            "generatedAt": "2026-08-07T06:00:00+00:00",
            "activeAlertCount": 3,
            "activeAlerts": ["a", "b", "ghost"],
            "quarantinedSourceCount": 2,
            "quarantinedSources": ["a", "b"],
            "probationSourceCount": 0,
            "probationSources": [],
            "sources": {
                "a": {
                    "id": "a",
                    "alertActive": True,
                    "collectionState": "quarantined",
                    "priority": "normal",
                },
                "b": {
                    "id": "b",
                    "alertActive": True,
                    "collectionState": "probation",
                    "priority": "low",
                    "performance": {"reviewRequired": True, "reviewState": "monitor"},
                },
            },
        }

    def test_rebuild_changes_only_aggregate_fields(self) -> None:
        payload = self.stale_payload()
        before_sources = copy.deepcopy(payload["sources"])
        normalized = rebuild_source_health_summary(payload)
        self.assertEqual(normalized["sources"], before_sources)
        self.assertEqual(normalized["activeAlertCount"], 2)
        self.assertEqual(normalized["activeAlerts"], ["a", "b"])
        self.assertEqual(normalized["quarantinedSources"], ["a"])
        self.assertEqual(normalized["probationSources"], ["b"])
        self.assertEqual(normalized["lowPrioritySources"], ["b"])
        self.assertEqual(normalized["performanceReviewSources"], ["b"])
        self.assertEqual(normalized["monitorSources"], ["b"])
        self.assertEqual(normalized["generatedAt"], payload["generatedAt"])

    def test_rebuild_is_idempotent(self) -> None:
        first = rebuild_source_health_summary(self.stale_payload())
        second = rebuild_source_health_summary(first)
        self.assertEqual(first, second)

    def test_governance_reports_summary_only_fixed_point_drift(self) -> None:
        config = {"tracks": [], "sources": []}
        ledger = {"added": [], "removed": []}
        payload = self.stale_payload()
        # Use non-auto health rows so governance has no row deletion reason.
        _, _, normalized, stats = normalize_tracking_sources(config, ledger, payload)
        self.assertEqual(normalized["sources"], payload["sources"])
        self.assertTrue(stats["healthSummaryChanged"])
        self.assertEqual(stats["healthRowsRemoved"], 0)


if __name__ == "__main__":
    unittest.main()
