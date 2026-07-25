from __future__ import annotations

import unittest

from tools.validate_user_source_coverage import evaluate_coverage


def source(
    source_id: str,
    url: str,
    *,
    source_type: str = "listing-search",
    category: str = "media",
) -> dict:
    return {
        "id": source_id,
        "name": source_id,
        "url": url,
        "sourceType": source_type,
        "sourceCategory": category,
        "region": "全球",
        "sector": "AI / AGI",
        "company": "",
        "ticker": "",
        "keywords": [],
        "enabled": True,
    }


class UserSourceCoverageTests(unittest.TestCase):
    def test_adaptive_public_source_with_status_passes(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("yahoo", "https://tw.yahoo.com/?p=us")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-yahoo",
                    "status": "ok",
                    "accepted": 3,
                    "adapter": "adaptive-public-v1",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["attemptedRuntimeStatuses"], 1)
        self.assertEqual(report["productiveRuntimeStatuses"], 1)
        self.assertEqual(report["missingStatuses"], [])
        self.assertEqual(report["adapterMismatches"], [])

    def test_missing_status_fails(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("example", "https://example.com/news")],
        }

        report = evaluate_coverage(config, {"sourceStatus": []})

        self.assertFalse(report["passed"])
        self.assertEqual(report["missingStatuses"], ["user-source-example"])

    def test_generic_website_cannot_bypass_adaptive_adapter(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("example", "https://example.com/news")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-example",
                    "status": "ok",
                    "accepted": 1,
                    "adapter": "generic-web-v2",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertFalse(report["passed"])
        self.assertEqual(report["adapterMismatches"][0]["actual"], "generic-web-v2")

    def test_x_direct_source_only_requires_diagnostic_status(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("washington-post", "https://x.com/washingtonpost")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-washington-post",
                    "status": "error",
                    "accepted": 0,
                    "failed": 1,
                    "platform": "X",
                    "error": "HTTP 429",
                }
            ]
        }

        report = evaluate_coverage(config, snapshot)

        self.assertTrue(report["passed"])
        self.assertEqual(report["attemptedRuntimeStatuses"], 1)
        self.assertEqual(report["productiveRuntimeStatuses"], 0)

    def test_google_alerts_settings_page_only_requires_explicit_error(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("alerts", "https://www.google.com/alerts")],
        }
        snapshot = {
            "sourceStatus": [
                {
                    "id": "user-source-alerts",
                    "status": "error",
                    "accepted": 0,
                    "failed": 1,
                    "platform": "Google Alerts",
                    "error": "not a public content feed",
                }
            ]
        }

        self.assertTrue(evaluate_coverage(config, snapshot)["passed"])

    def test_invalid_enabled_url_is_unroutable(self) -> None:
        config = {
            "schemaVersion": 1,
            "tracks": [],
            "sources": [source("bad", "not-a-url")],
        }

        report = evaluate_coverage(config, {"sourceStatus": []})

        self.assertFalse(report["passed"])
        self.assertEqual(report["unroutableSources"][0]["id"], "bad")


if __name__ == "__main__":
    unittest.main()
