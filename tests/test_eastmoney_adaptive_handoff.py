from __future__ import annotations

import unittest

from tools import crawl_official_with_tracking as tracking_crawler
from tools import eastmoney_transport as transport


def article(article_id: str, source_id: str, url: str) -> dict:
    return {
        "id": article_id,
        "sourceId": source_id,
        "title": article_id,
        "source": {
            "name": "东方财富" if "eastmoney" in url else "Example",
            "url": url,
        },
    }


class EastmoneyAdaptiveHandoffTests(unittest.TestCase):
    def test_strict_publisher_removes_only_generic_eastmoney_articles(self) -> None:
        official = tracking_crawler.official
        original = official.load_existing_payload
        payload = {
            "articles": [
                article(
                    "generic-detail",
                    "user-source-eastmoney",
                    "https://finance.eastmoney.com/a/202607253821110827.html",
                ),
                article(
                    "generic-channel",
                    "user-source-eastmoney",
                    "https://finance.eastmoney.com/",
                ),
                article(
                    "official-detail",
                    "official-user-东方财富",
                    "https://finance.eastmoney.com/a/202607253821110592.html",
                ),
                article(
                    "other-source",
                    "user-source-example",
                    "https://example.com/news/ai-launch",
                ),
            ],
            "sourceStatus": [
                {
                    "id": "user-source-eastmoney",
                    "adapter": "adaptive-public-v1",
                    "publisherHandoff": "eastmoney-strict-detail",
                    "handoffStatusId": "official-user-东方财富",
                },
                {"id": "official-user-东方财富", "accepted": 1},
            ],
        }

        try:
            official.load_existing_payload = lambda _path=official.OUTPUT_PATH: payload
            transport.install_handoff_cleanup()
            loaded = official.load_existing_payload()
        finally:
            official.load_existing_payload = original

        self.assertEqual(
            [item["id"] for item in loaded["articles"]],
            ["official-detail", "other-source"],
        )
        self.assertEqual(loaded["sourceStatus"], payload["sourceStatus"])

    def test_non_eastmoney_generic_detail_is_never_removed(self) -> None:
        official = tracking_crawler.official
        original = official.load_existing_payload
        payload = {
            "articles": [
                article(
                    "yahoo-detail",
                    "user-source-yahoo",
                    "https://tw.news.yahoo.com/ai-funding.html",
                )
            ],
            "sourceStatus": [],
        }

        try:
            official.load_existing_payload = lambda _path=official.OUTPUT_PATH: payload
            transport.install_handoff_cleanup()
            loaded = official.load_existing_payload()
        finally:
            official.load_existing_payload = original

        self.assertEqual([item["id"] for item in loaded["articles"]], ["yahoo-detail"])


if __name__ == "__main__":
    unittest.main()
