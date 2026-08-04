from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.update_source_health import DEFAULT_POLICY, update_health


def payload(status: dict, articles: list[dict] | None = None) -> dict:
    return {"sourceStatus": [status], "articles": articles or []}


def graded_article(source_id: str, grade: str) -> dict:
    return {
        "sourceId": source_id,
        "source": {"evidenceGrade": grade},
    }


class SourceHealthTest(unittest.TestCase):
    def test_three_explicit_errors_trigger_and_success_recovers(self) -> None:
        state: dict = {}
        base = datetime(2026, 7, 29, tzinfo=UTC)
        status = {
            "id": "source-a",
            "name": "Source A",
            "platform": "网站",
            "status": "error",
            "accepted": 0,
            "error": "HTTP 503",
        }
        for offset in range(3):
            state, summary = update_health(
                state,
                payload(status, [graded_article("source-a", "C")]),
                DEFAULT_POLICY,
                now=base + timedelta(hours=offset),
            )
        self.assertEqual(summary["newAlerts"], ["source-a"])
        self.assertEqual(state["activeAlerts"], ["source-a"])
        self.assertEqual(state["sources"]["source-a"]["consecutiveFailures"], 3)

        recovered = dict(status, status="ok", accepted=2, error="")
        state, summary = update_health(
            state,
            payload(recovered, [graded_article("source-a", "C")]),
            DEFAULT_POLICY,
            now=base + timedelta(hours=4),
        )
        self.assertEqual(summary["recoveries"], ["source-a"])
        self.assertEqual(state["activeAlerts"], [])
        self.assertEqual(state["sources"]["source-a"]["consecutiveFailures"], 0)

    def test_critical_wechat_empty_counts_as_failure(self) -> None:
        state, _ = update_health(
            {},
            payload(
                {
                    "id": "wechat-a",
                    "name": "微信源",
                    "platform": "微信",
                    "status": "empty",
                    "accepted": 0,
                }
            ),
            DEFAULT_POLICY,
            now=datetime(2026, 7, 29, tzinfo=UTC),
        )
        self.assertEqual(state["sources"]["wechat-a"]["consecutiveFailures"], 1)

    def test_noncritical_empty_does_not_trigger_failure(self) -> None:
        state, _ = update_health(
            {},
            payload(
                {
                    "id": "optional-feed",
                    "name": "可选 RSS",
                    "platform": "RSS",
                    "status": "empty",
                    "accepted": 0,
                }
            ),
            DEFAULT_POLICY,
            now=datetime(2026, 7, 29, tzinfo=UTC),
        )
        self.assertEqual(state["sources"]["optional-feed"]["consecutiveFailures"], 0)

    def test_grade_c_source_is_quarantined_after_seven_failures(self) -> None:
        state: dict = {}
        base = datetime(2026, 7, 1, tzinfo=UTC)
        status = {
            "id": "media-c",
            "name": "Media C",
            "platform": "专业媒体",
            "status": "error",
            "accepted": 0,
            "error": "HTTP 503",
        }
        for offset in range(7):
            state, summary = update_health(
                state,
                payload(status, [graded_article("media-c", "C")]),
                DEFAULT_POLICY,
                now=base + timedelta(days=offset),
            )
        entry = state["sources"]["media-c"]
        self.assertEqual(entry["collectionState"], "quarantined")
        self.assertFalse(entry["publicationEligible"])
        self.assertEqual(summary["quarantinedNow"], ["media-c"])

    def test_grade_a_source_alerts_but_is_never_auto_quarantined(self) -> None:
        state: dict = {}
        base = datetime(2026, 7, 1, tzinfo=UTC)
        status = {
            "id": "sec",
            "name": "SEC",
            "platform": "SEC",
            "status": "error",
            "accepted": 0,
            "error": "HTTP 503",
        }
        for offset in range(9):
            state, _ = update_health(
                state,
                payload(status, [graded_article("sec", "A")]),
                DEFAULT_POLICY,
                now=base + timedelta(days=offset),
            )
        entry = state["sources"]["sec"]
        self.assertEqual(entry["collectionState"], "active")
        self.assertTrue(entry["alertActive"])

    def test_three_productive_probes_restore_quarantined_source(self) -> None:
        previous = {
            "sources": {
                "media-c": {
                    "id": "media-c",
                    "name": "Media C",
                    "platform": "专业媒体",
                    "evidenceGrade": "C",
                    "collectionState": "quarantined",
                    "publicationEligible": False,
                    "consecutiveFailures": 7,
                    "recoverySuccesses": 0,
                    "alertActive": True,
                    "firstObservedAt": "2026-07-01T00:00:00+00:00",
                    "lastProductiveAt": "2026-06-30T00:00:00+00:00",
                }
            }
        }
        status = {
            "id": "media-c",
            "name": "Media C",
            "platform": "专业媒体",
            "status": "ok",
            "accepted": 2,
        }
        base = datetime(2026, 8, 1, tzinfo=UTC)
        state = previous
        for offset in range(2):
            state, _ = update_health(
                state,
                payload(status, [graded_article("media-c", "C")]),
                DEFAULT_POLICY,
                now=base + timedelta(days=offset),
            )
            self.assertEqual(state["sources"]["media-c"]["collectionState"], "probation")
        state, summary = update_health(
            state,
            payload(status, [graded_article("media-c", "C")]),
            DEFAULT_POLICY,
            now=base + timedelta(days=2),
        )
        self.assertEqual(state["sources"]["media-c"]["collectionState"], "active")
        self.assertTrue(state["sources"]["media-c"]["publicationEligible"])
        self.assertEqual(summary["resumedNow"], ["media-c"])

    def test_thirty_days_without_productive_output_lowers_priority(self) -> None:
        previous = {
            "sources": {
                "optional-feed": {
                    "id": "optional-feed",
                    "name": "Optional",
                    "platform": "RSS",
                    "evidenceGrade": "C",
                    "collectionState": "active",
                    "alertActive": False,
                    "consecutiveFailures": 0,
                    "firstObservedAt": "2026-06-01T00:00:00+00:00",
                    "lastProductiveAt": "2026-06-01T00:00:00+00:00",
                }
            }
        }
        state, _ = update_health(
            previous,
            payload(
                {
                    "id": "optional-feed",
                    "name": "Optional",
                    "platform": "RSS",
                    "status": "empty",
                    "accepted": 0,
                },
                [graded_article("optional-feed", "C")],
            ),
            DEFAULT_POLICY,
            now=datetime(2026, 7, 5, tzinfo=UTC),
        )
        entry = state["sources"]["optional-feed"]
        self.assertEqual(entry["priority"], "low")
        self.assertGreaterEqual(entry["inactiveDays"], 30)

    def test_missing_status_preserves_previous_cross_run_state(self) -> None:
        previous = {
            "sources": {
                "missing-source": {
                    "id": "missing-source",
                    "collectionState": "quarantined",
                    "alertActive": True,
                    "evidenceGrade": "D",
                }
            }
        }
        state, _ = update_health(
            previous,
            {"sourceStatus": [], "articles": []},
            DEFAULT_POLICY,
            now=datetime(2026, 7, 5, tzinfo=UTC),
        )
        self.assertEqual(
            state["sources"]["missing-source"]["collectionState"],
            "quarantined",
        )
        self.assertTrue(state["sources"]["missing-source"]["missingFromCurrentRun"])


if __name__ == "__main__":
    unittest.main()
