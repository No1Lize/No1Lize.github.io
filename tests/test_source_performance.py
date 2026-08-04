from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.source_performance import (
    annotate_publication_metrics,
    new_article_metrics,
    update_source_performance,
)


class SourcePerformanceTest(unittest.TestCase):
    def test_publication_metrics_separate_duplicates_from_quarantine(self) -> None:
        incoming = [
            {
                "id": "a-1",
                "sourceId": "source-a",
                "source": {"url": "https://example.com/a?utm_source=one"},
            },
            {
                "id": "a-2",
                "sourceId": "source-a",
                "source": {"url": "https://example.com/a?utm_source=two"},
            },
            {
                "id": "a-3",
                "sourceId": "source-a",
                "source": {"url": "https://example.com/b"},
            },
            {
                "id": "b-1",
                "sourceId": "source-b",
                "source": {"url": "https://example.net/a"},
            },
        ]
        published = [incoming[0], incoming[2]]
        statuses = [{"id": "source-a"}, {"id": "source-b"}]

        annotate_publication_metrics(
            incoming,
            published,
            statuses,
            withheld_source_ids={"source-b"},
        )

        self.assertEqual(statuses[0]["candidateCount"], 3)
        self.assertEqual(statuses[0]["uniqueCandidateCount"], 2)
        self.assertEqual(statuses[0]["publishedCount"], 2)
        self.assertEqual(statuses[0]["duplicateCount"], 1)
        self.assertEqual(statuses[0]["withheldCount"], 0)
        self.assertEqual(statuses[1]["withheldCount"], 1)
        self.assertEqual(statuses[1]["duplicateCount"], 0)

    def test_new_article_metrics_only_count_exact_sightings_since_previous_run(self) -> None:
        payload = {
            "articles": [
                {
                    "id": "new",
                    "sourceId": "source-a",
                    "publishedAt": "2026-08-01",
                    "firstSeenAt": "2026-08-04T01:00:00Z",
                    "firstSeenEstimated": False,
                },
                {
                    "id": "old",
                    "sourceId": "source-a",
                    "publishedAt": "2026-08-01",
                    "firstSeenAt": "2026-08-02T01:00:00Z",
                    "firstSeenEstimated": False,
                },
                {
                    "id": "estimated",
                    "sourceId": "source-a",
                    "publishedAt": "2026-08-01",
                    "firstSeenAt": "2026-08-04T01:00:00Z",
                    "firstSeenEstimated": True,
                },
            ]
        }
        metrics = new_article_metrics(
            payload,
            previous_generated_at="2026-08-03T00:00:00Z",
            now=datetime(2026, 8, 4, 3, tzinfo=UTC),
        )
        self.assertEqual(metrics["source-a"]["newArticleCount"], 1)
        self.assertEqual(metrics["source-a"]["discoveryLagDayTotal"], 3)
        self.assertEqual(metrics["source-a"]["discoveryLagSampleCount"], 1)

    def test_rolling_metrics_recommend_retiring_persistently_unproductive_c_source(self) -> None:
        performance: dict = {}
        base = datetime(2026, 7, 1, tzinfo=UTC)
        policy = {
            "performanceWindowRuns": 30,
            "performanceMinimumRuns": 5,
            "retirementMinimumRuns": 10,
            "minimumAvailabilityRate": 0.6,
            "minimumProductiveRate": 0.15,
            "retirementMaximumAvailabilityRate": 0.2,
            "retirementMaximumProductiveRate": 0.05,
        }
        for offset in range(10):
            performance = update_source_performance(
                performance,
                {
                    "id": "source-c",
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 1,
                    "candidateCount": 0,
                    "publishedCount": 0,
                    "duplicateCount": 0,
                },
                None,
                evidence_grade="C",
                collection_state="quarantined",
                priority="normal",
                manual_quality=None,
                policy=policy,
                now=base + timedelta(days=offset),
            )

        self.assertEqual(performance["runs"], 10)
        self.assertEqual(performance["availabilityRate"], 0.0)
        self.assertEqual(performance["productiveRate"], 0.0)
        self.assertEqual(performance["reviewState"], "retire-candidate")
        self.assertIn("low-availability", performance["reviewReasons"])
        self.assertIn("quarantined", performance["reviewReasons"])

    def test_a_grade_source_is_monitored_not_auto_retired(self) -> None:
        performance: dict = {}
        base = datetime(2026, 7, 1, tzinfo=UTC)
        for offset in range(10):
            performance = update_source_performance(
                performance,
                {"id": "regulator", "status": "error", "failed": 1},
                None,
                evidence_grade="A",
                collection_state="active",
                priority="normal",
                manual_quality=None,
                policy={},
                now=base + timedelta(days=offset),
            )
        self.assertEqual(performance["reviewState"], "monitor")

    def test_manual_misattribution_enters_review_reasons(self) -> None:
        performance: dict = {}
        base = datetime(2026, 7, 1, tzinfo=UTC)
        manual = {
            "reviewedRecords": 20,
            "misattributedRecords": 2,
            "confirmedDuplicateRecords": 0,
            "misattributionRate": 0.1,
        }
        for offset in range(5):
            performance = update_source_performance(
                performance,
                {
                    "id": "media",
                    "status": "ok",
                    "scanned": 10,
                    "accepted": 5,
                    "candidateCount": 5,
                    "publishedCount": 5,
                    "duplicateCount": 0,
                },
                None,
                evidence_grade="C",
                collection_state="active",
                priority="normal",
                manual_quality=manual,
                policy={"maximumMisattributionRate": 0.05},
                now=base + timedelta(days=offset),
            )
        self.assertIn("manual-misattribution", performance["reviewReasons"])
        self.assertTrue(performance["reviewRequired"])


if __name__ == "__main__":
    unittest.main()
