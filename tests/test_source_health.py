from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from tools.update_source_health import DEFAULT_POLICY, update_health


def payload(status: dict) -> dict:
    return {"sourceStatus": [status]}


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
                payload(status),
                DEFAULT_POLICY,
                now=base + timedelta(hours=offset),
            )
        self.assertEqual(summary["newAlerts"], ["source-a"])
        self.assertEqual(state["activeAlerts"], ["source-a"])
        self.assertEqual(state["sources"]["source-a"]["consecutiveFailures"], 3)

        recovered = dict(status, status="ok", accepted=2, error="")
        state, summary = update_health(
            state,
            payload(recovered),
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


if __name__ == "__main__":
    unittest.main()
