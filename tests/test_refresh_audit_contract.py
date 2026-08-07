from __future__ import annotations

import json
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tools import crawl_articles
from tools import frequent_refresh_due


class RefreshAuditContractTests(unittest.TestCase):
    def test_core_crawler_preserves_refresh_and_tracking_metadata(self) -> None:
        previous = {
            "schemaVersion": 3,
            "generatedAt": "2026-08-07T01:00:00+00:00",
            "articleCount": 0,
            "articles": [],
            "companyFacts": {},
            "sourceStatus": [],
            "qualityGate": {},
            "refreshAudit": {
                "mode": "full",
                "pipelineCompleted": True,
                "completedAt": "2026-08-07T01:00:00+00:00",
                "lastNewsCrawlAt": "2026-08-07T01:00:00+00:00",
            },
            "trackingConfigHash": "abc",
            "trackingEnrichedAt": "2026-08-07T01:00:01+00:00",
            "trackCoverage": {"ai": {"status": "ready"}},
        }
        with tempfile.TemporaryDirectory(dir=crawl_articles.ROOT) as directory:
            output = Path(directory) / "articles.json"
            changed = crawl_articles.write_if_changed(
                [{"id": "new"}],
                previous,
                output_path=output,
            )
            self.assertTrue(changed)
            result = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(result["refreshAudit"], previous["refreshAudit"])
        self.assertEqual(result["trackingConfigHash"], "abc")
        self.assertEqual(result["trackCoverage"], previous["trackCoverage"])

    def test_missing_audit_is_due_even_when_generated_at_is_recent(self) -> None:
        now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        result = frequent_refresh_due.evaluate_due(
            {"generatedAt": (now - timedelta(minutes=5)).isoformat()},
            event_name="schedule",
            now=now,
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["reason"], "missing-news-crawl-audit")

    def test_due_check_uses_last_real_news_crawl(self) -> None:
        now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        payload = {
            "generatedAt": (now - timedelta(minutes=5)).isoformat(),
            "refreshAudit": {
                "mode": "frequent",
                "pipelineCompleted": True,
                "completedAt": (now - timedelta(minutes=120)).isoformat(),
                "lastNewsCrawlAt": (now - timedelta(minutes=120)).isoformat(),
                "stages": ["core-and-tracking-sources"],
            },
        }
        result = frequent_refresh_due.evaluate_due(
            payload,
            event_name="schedule",
            now=now,
        )
        self.assertTrue(result["due"])
        self.assertEqual(result["ageMinutes"], 120)

    def test_old_completed_full_audit_is_backward_compatible(self) -> None:
        now = datetime(2026, 8, 7, 10, 0, tzinfo=UTC)
        payload = {
            "refreshAudit": {
                "mode": "full",
                "pipelineCompleted": True,
                "completedAt": (now - timedelta(minutes=30)).isoformat(),
                "stages": ["core-and-tracking-sources"],
            }
        }
        result = frequent_refresh_due.evaluate_due(
            payload,
            event_name="schedule",
            now=now,
        )
        self.assertFalse(result["due"])
        self.assertEqual(result["ageMinutes"], 30)


if __name__ == "__main__":
    unittest.main()
