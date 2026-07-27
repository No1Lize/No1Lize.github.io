from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import crawl_articles
from tools import snapshot_retention


def article(article_id: str, published_at: str, importance: int = 70) -> dict:
    return {
        "id": article_id,
        "sourceId": "test-source",
        "title": f"Article {article_id}",
        "summary": "Snapshot rolling-retention test article.",
        "type": "公司动态",
        "region": "全球",
        "sector": "AI / AGI",
        "company": "科技产业",
        "publishedAt": published_at,
        "importance": importance,
        "source": {
            "name": "Test",
            "url": f"https://example.com/{article_id}",
            "level": "媒体报道",
            "platform": "Test",
        },
    }


class SnapshotRetentionTest(unittest.TestCase):
    def test_newest_articles_displace_oldest_at_capacity(self) -> None:
        rows = [
            article("oldest", "2026-07-01"),
            article("middle", "2026-07-02"),
            article("newest", "2026-07-03"),
        ]
        retained = snapshot_retention.retain_latest_articles(rows, capacity=2)
        self.assertEqual([row["id"] for row in retained], ["newest", "middle"])

    def test_same_day_uses_importance_then_id_deterministically(self) -> None:
        rows = [
            article("a", "2026-07-03", 70),
            article("b", "2026-07-03", 90),
            article("c", "2026-07-03", 90),
        ]
        retained = snapshot_retention.retain_latest_articles(rows, capacity=2)
        self.assertEqual([row["id"] for row in retained], ["c", "b"])

    def test_payload_records_the_formal_retention_policy(self) -> None:
        payload = {
            "schemaVersion": 3,
            "articleCount": 3,
            "articles": [
                article("oldest", "2026-07-01"),
                article("newest", "2026-07-03"),
                article("middle", "2026-07-02"),
            ],
        }
        next_payload, removed = snapshot_retention.apply_retention(payload, capacity=2)
        self.assertEqual(removed, 1)
        self.assertEqual(next_payload["articleCount"], 2)
        self.assertEqual(
            [row["id"] for row in next_payload["articles"]],
            ["newest", "middle"],
        )
        self.assertEqual(
            next_payload["snapshotRetention"]["overflowAction"],
            "discard-oldest",
        )
        self.assertEqual(snapshot_retention.validate_retention(next_payload, 2), [])

    def test_core_merge_already_applies_the_same_replacement_rule(self) -> None:
        existing = [
            article("oldest", "2026-07-01"),
            article("middle", "2026-07-02"),
        ]
        incoming = [article("newest", "2026-07-03")]
        with patch.object(crawl_articles, "MAX_ARTICLES", 2):
            merged = crawl_articles.merge_articles(existing, incoming)
        self.assertEqual([row["id"] for row in merged], ["newest", "middle"])


if __name__ == "__main__":
    unittest.main()
