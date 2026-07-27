from __future__ import annotations

import unittest

from tools.eastmoney_transport import merge_eastmoney_history


SOURCE_ID = "official-user-东方财富"


def article(
    article_id: str,
    *,
    sequence: int,
    published_at: str = "2026-07-25",
    importance: int = 80,
    source_id: str = SOURCE_ID,
    title: str | None = None,
) -> dict:
    return {
        "id": article_id,
        "sourceId": source_id,
        "title": title or f"东方财富科技文章 {sequence}",
        "summary": "半导体与人工智能产业进展。",
        "company": "科技产业",
        "publishedAt": published_at,
        "importance": importance,
        "source": {
            "name": "东方财富",
            "url": f"https://finance.eastmoney.com/a/20260725{3821000000 + sequence}.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }


def status(accepted: int = 1) -> dict:
    return {
        "id": SOURCE_ID,
        "name": "东方财富 官方动态",
        "company": "东方财富",
        "status": "ok",
        "accepted": accepted,
        "failed": 0,
        "platform": "东方财富",
    }


class EastmoneyRollingHistoryTests(unittest.TestCase):
    def test_successful_batch_keeps_new_and_previous_details(self) -> None:
        existing = [article("old", sequence=1, published_at="2026-07-24")]
        incoming = [article("new", sequence=2, published_at="2026-07-25")]
        public_status = status()

        merged = merge_eastmoney_history(existing, incoming, [public_status])

        self.assertEqual([item["id"] for item in merged], ["new", "old"])
        self.assertEqual(public_status["newAccepted"], 1)
        self.assertEqual(public_status["accepted"], 2)
        self.assertTrue(public_status["retainedPrevious"])
        self.assertEqual(public_status["retainedPreviousCount"], 1)

    def test_incoming_copy_replaces_cached_copy_with_same_url(self) -> None:
        cached = article("cached", sequence=3, importance=70, title="旧标题")
        incoming = dict(cached)
        incoming["id"] = "fresh"
        incoming["title"] = "更新后的标题"
        incoming["importance"] = 90
        public_status = status()

        merged = merge_eastmoney_history([cached], [incoming], [public_status])

        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "fresh")
        self.assertEqual(merged[0]["title"], "更新后的标题")
        self.assertEqual(public_status["newAccepted"], 1)
        self.assertEqual(public_status["accepted"], 1)
        self.assertNotIn("retainedPrevious", public_status)

    def test_history_is_bounded_to_newest_articles(self) -> None:
        existing = [
            article(
                f"old-{index}",
                sequence=index,
                published_at=f"2026-07-{index:02d}",
            )
            for index in range(1, 13)
        ]
        incoming = [article("newest", sequence=20, published_at="2026-07-25")]
        public_status = status()

        merged = merge_eastmoney_history(
            existing,
            incoming,
            [public_status],
            limit=5,
        )

        self.assertEqual(len(merged), 5)
        self.assertEqual(merged[0]["id"], "newest")
        self.assertNotIn("old-1", {item["id"] for item in merged})
        self.assertEqual(public_status["accepted"], 5)
        self.assertEqual(public_status["retainedPreviousCount"], 4)

    def test_same_day_sort_uses_importance(self) -> None:
        existing = [
            article("low", sequence=30, importance=60),
            article("high", sequence=31, importance=95),
        ]
        incoming = [article("medium", sequence=32, importance=80)]
        public_status = status()

        merged = merge_eastmoney_history(
            existing,
            incoming,
            [public_status],
            limit=3,
        )

        self.assertEqual(
            [item["id"] for item in merged],
            ["high", "medium", "low"],
        )

    def test_non_eastmoney_sources_are_not_merged_or_removed(self) -> None:
        other = article(
            "other",
            sequence=40,
            source_id="official-example-company",
        )
        other["source"] = {
            "name": "Example Company",
            "url": "https://example.com/news/40",
            "level": "官方披露",
            "platform": "官方网站",
        }
        incoming = [other, article("eastmoney-new", sequence=41)]
        public_status = status()

        merged = merge_eastmoney_history([], incoming, [public_status])

        self.assertEqual(
            {item["id"] for item in merged},
            {"other", "eastmoney-new"},
        )

    def test_empty_discovery_does_not_change_incoming_batch(self) -> None:
        incoming = [article("unrelated-incoming", sequence=50)]
        public_status = status(accepted=0)
        public_status["status"] = "empty"

        merged = merge_eastmoney_history([], incoming, [public_status])

        self.assertEqual(merged, incoming)
        self.assertNotIn("newAccepted", public_status)


if __name__ == "__main__":
    unittest.main()
