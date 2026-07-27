from __future__ import annotations

import unittest

from tools import crawl_official_companies as official
from tools.eastmoney_transport import replacement_statuses_for_eastmoney


SOURCE_ID = "official-user-东方财富"
DETAIL_URL = "https://finance.eastmoney.com/a/202607253821108344.html"


def article(
    article_id: str,
    source_id: str = SOURCE_ID,
    url: str = DETAIL_URL,
) -> dict:
    return {
        "id": article_id,
        "sourceId": source_id,
        "title": "TCL科技收购广州华星半导体股权",
        "summary": "TCL科技公布半导体并购事项。",
        "company": "科技产业",
        "publishedAt": "2026-07-25",
        "importance": 80,
        "source": {
            "name": "东方财富",
            "url": url,
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }


def status(
    *,
    source_id: str = SOURCE_ID,
    name: str = "东方财富 官方动态",
    accepted: int = 0,
    state: str = "empty",
    failed: int = 0,
) -> dict:
    return {
        "id": source_id,
        "name": name,
        "company": "东方财富",
        "status": state,
        "accepted": accepted,
        "failed": failed,
        "platform": "东方财富",
    }


class EastmoneySnapshotRetentionTests(unittest.TestCase):
    def test_empty_discovery_retains_existing_detail_batch(self) -> None:
        existing = [article("eastmoney-old")]
        public_status = status()

        replacement_statuses = replacement_statuses_for_eastmoney(
            existing,
            [public_status],
        )
        merged = official.replace_official_source_batches(
            existing,
            [],
            replacement_statuses,
        )

        self.assertEqual([item["id"] for item in merged], ["eastmoney-old"])
        self.assertEqual(replacement_statuses[0]["status"], "error")
        self.assertEqual(public_status["status"], "partial")
        self.assertTrue(public_status["retainedPrevious"])
        self.assertIn("previous detail snapshot retained", public_status["error"])

    def test_successful_incoming_batch_replaces_existing_details(self) -> None:
        existing = [article("eastmoney-old")]
        incoming = [
            article(
                "eastmoney-new",
                url="https://finance.eastmoney.com/a/202607263821999999.html",
            )
        ]
        public_status = status(accepted=1, state="ok")

        replacement_statuses = replacement_statuses_for_eastmoney(
            existing,
            [public_status],
        )
        merged = official.replace_official_source_batches(
            existing,
            incoming,
            replacement_statuses,
        )

        self.assertEqual([item["id"] for item in merged], ["eastmoney-new"])
        self.assertEqual(replacement_statuses[0]["status"], "ok")
        self.assertNotIn("retainedPrevious", public_status)

    def test_non_detail_legacy_page_does_not_enable_retention(self) -> None:
        existing = [
            article(
                "eastmoney-channel",
                url="https://fund.eastmoney.com/a/cjjyw.html",
            )
        ]
        public_status = status()

        replacement_statuses = replacement_statuses_for_eastmoney(
            existing,
            [public_status],
        )
        merged = official.replace_official_source_batches(
            existing,
            [],
            replacement_statuses,
        )

        self.assertEqual(merged, [])
        self.assertEqual(replacement_statuses[0]["status"], "empty")
        self.assertNotIn("retainedPrevious", public_status)

    def test_other_sources_keep_shared_empty_replacement_behavior(self) -> None:
        other_source_id = "official-example-company"
        existing = [
            {
                **article("other-old", source_id=other_source_id),
                "source": {
                    "name": "Example Company",
                    "url": "https://example.com/news/old",
                    "level": "官方披露",
                    "platform": "官方网站",
                },
            }
        ]
        public_status = status(
            source_id=other_source_id,
            name="Example Company 官方动态",
        )
        public_status["company"] = "Example Company"

        replacement_statuses = replacement_statuses_for_eastmoney(
            existing,
            [public_status],
        )
        merged = official.replace_official_source_batches(
            existing,
            [],
            replacement_statuses,
        )

        self.assertEqual(merged, [])
        self.assertEqual(replacement_statuses[0]["status"], "empty")
        self.assertNotIn("retainedPrevious", public_status)


if __name__ == "__main__":
    unittest.main()
