from __future__ import annotations

import unittest
from types import SimpleNamespace

from tools import crawl_official_with_tracking as tracking_crawler


DETAIL_URL = "https://finance.eastmoney.com/a/202607253821110827.html"
CHANNEL_URL = "https://fund.eastmoney.com/a/cjjyw.html"
OFFICIAL_SOURCE_ID = "official-user-东方财富"


def article(article_id: str, source_id: str, url: str, source_name: str = "东方财富") -> dict:
    return {
        "id": article_id,
        "sourceId": source_id,
        "title": f"测试文章 {article_id}",
        "summary": "人工智能与半导体产业进展。",
        "type": "公司动态",
        "region": "全球",
        "sector": "半导体",
        "company": "科技产业",
        "publishedAt": "2026-07-25",
        "importance": 80,
        "source": {
            "name": source_name,
            "url": url,
            "level": "媒体报道",
            "platform": source_name,
        },
    }


class EastmoneyFallbackPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        official = tracking_crawler.official
        self.official = official
        self.original_load_existing_payload = official.load_existing_payload
        self.original_load_registry = official.load_registry
        self.original_article_from_page = official._article_from_page

    def tearDown(self) -> None:
        self.official.load_existing_payload = self.original_load_existing_payload
        self.official.load_registry = self.original_load_registry
        self.official._article_from_page = self.original_article_from_page

    def install_with_payload(self, payload: dict, active: bool = True) -> None:
        self.official.load_existing_payload = lambda path=self.official.OUTPUT_PATH: payload
        specs = [SimpleNamespace(source_id=OFFICIAL_SOURCE_ID)] if active else []
        tracking_crawler.install_overrides([], specs, [])

    def test_generic_channel_record_is_removed(self) -> None:
        payload = {
            "articles": [
                article("channel", "user-source-eastmoney", CHANNEL_URL),
            ],
            "sourceStatus": [],
        }
        self.install_with_payload(payload)

        loaded = self.official.load_existing_payload()

        self.assertEqual(loaded["articles"], [])

    def test_concrete_generic_detail_record_is_preserved(self) -> None:
        fallback = article("detail", "user-source-eastmoney", DETAIL_URL)
        payload = {
            "articles": [fallback],
            "sourceStatus": [],
        }
        self.install_with_payload(payload)

        loaded = self.official.load_existing_payload()

        self.assertEqual(loaded["articles"], [fallback])

    def test_non_eastmoney_generic_record_is_unchanged(self) -> None:
        other = article(
            "other",
            "user-source-example",
            "https://example.com/news/1",
            source_name="Example Media",
        )
        payload = {
            "articles": [other],
            "sourceStatus": [],
        }
        self.install_with_payload(payload)

        loaded = self.official.load_existing_payload()

        self.assertEqual(loaded["articles"], [other])

    def test_inactive_official_user_record_is_still_removed(self) -> None:
        official_detail = article("official", OFFICIAL_SOURCE_ID, DETAIL_URL)
        payload = {
            "articles": [official_detail],
            "sourceStatus": [
                {
                    "id": OFFICIAL_SOURCE_ID,
                    "name": "东方财富 官方动态",
                    "status": "ok",
                    "accepted": 1,
                }
            ],
        }
        self.install_with_payload(payload, active=False)

        loaded = self.official.load_existing_payload()

        self.assertEqual(loaded["articles"], [])
        self.assertEqual(loaded["sourceStatus"], [])


if __name__ == "__main__":
    unittest.main()
