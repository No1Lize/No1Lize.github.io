from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.update_source_health import DEFAULT_POLICY, update_health


class SourceHealthPerformanceIntegrationTest(unittest.TestCase):
    def test_health_state_persists_rolling_performance_metrics(self) -> None:
        state: dict = {}
        base = datetime(2026, 8, 1, tzinfo=UTC)
        for offset in range(5):
            status = {
                "id": "source-a",
                "name": "Source A",
                "platform": "专业媒体",
                "status": "ok",
                "scanned": 10,
                "accepted": 5,
                "candidateCount": 5,
                "publishedCount": 4,
                "duplicateCount": 1,
                "withheldCount": 0,
            }
            state, _ = update_health(
                state,
                {
                    "sourceStatus": [status],
                    "articles": [
                        {
                            "id": f"article-{offset}",
                            "sourceId": "source-a",
                            "publishedAt": (base + timedelta(days=offset - 1)).date().isoformat(),
                            "firstSeenAt": (base + timedelta(days=offset)).isoformat(),
                            "firstSeenEstimated": False,
                            "source": {"evidenceGrade": "C"},
                        }
                    ],
                },
                DEFAULT_POLICY,
                now=base + timedelta(days=offset, hours=1),
            )

        entry = state["sources"]["source-a"]
        performance = entry["performance"]
        self.assertEqual(state["schemaVersion"], 3)
        self.assertEqual(performance["runs"], 5)
        self.assertEqual(performance["availabilityRate"], 1.0)
        self.assertEqual(performance["productiveRate"], 1.0)
        self.assertEqual(performance["validYieldRate"], 0.5)
        self.assertEqual(performance["duplicateRate"], 0.2)
        self.assertEqual(performance["newArticles"], 4)
        self.assertEqual(performance["averageDiscoveryLagDays"], 1.0)
        self.assertEqual(performance["reviewState"], "retain")

    def test_manual_review_metrics_flow_into_health_state(self) -> None:
        state: dict = {}
        base = datetime(2026, 8, 1, tzinfo=UTC)
        manual = {
            "source-a": {
                "reviewedRecords": 20,
                "misattributedRecords": 2,
                "confirmedDuplicateRecords": 1,
                "misattributionRate": 0.1,
                "lastReviewedAt": "2026-08-01T00:00:00Z",
            }
        }
        for offset in range(5):
            state, _ = update_health(
                state,
                {
                    "sourceStatus": [
                        {
                            "id": "source-a",
                            "name": "Source A",
                            "platform": "专业媒体",
                            "status": "ok",
                            "scanned": 10,
                            "accepted": 5,
                            "candidateCount": 5,
                            "publishedCount": 5,
                            "duplicateCount": 0,
                        }
                    ],
                    "articles": [
                        {
                            "sourceId": "source-a",
                            "source": {"evidenceGrade": "C"},
                        }
                    ],
                },
                DEFAULT_POLICY,
                now=base + timedelta(days=offset),
                manual_reviews=manual,
            )
        performance = state["sources"]["source-a"]["performance"]
        self.assertEqual(performance["manualQuality"]["reviewedRecords"], 20)
        self.assertIn("manual-misattribution", performance["reviewReasons"])
        self.assertEqual(performance["reviewState"], "monitor")


if __name__ == "__main__":
    unittest.main()
