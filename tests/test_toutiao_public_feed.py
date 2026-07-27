from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tools import toutiao_public_feed as feed


class ToutiaoPublicFeedTests(unittest.TestCase):
    @staticmethod
    def _crawler() -> SimpleNamespace:
        def external_article(spec, **kwargs):
            return {
                "sourceId": spec["id"],
                "title": kwargs["title"],
                "summary": kwargs["summary"],
                "publishedAt": kwargs["published_at"],
                "source": {
                    "name": kwargs["source_name"],
                    "url": kwargs["url"],
                    "platform": kwargs["platform"],
                },
            }

        return SimpleNamespace(
            clean_title=lambda value: str(value).strip(),
            strip_html=lambda value: str(value).strip(),
            clean_text=lambda value: str(value).strip(),
            normalize_date=lambda value: str(value) if value else None,
            _matches_keywords=lambda _title, _summary, keywords, title_only=False: not keywords or True,
            _matches_required_keywords=lambda _title, _summary, keywords, title_only=False: not keywords or True,
            _external_article=external_article,
            _status=lambda source_id, name, status, scanned, accepted, **kwargs: {
                "id": source_id,
                "name": name,
                "status": status,
                "scanned": scanned,
                "accepted": accepted,
                **kwargs,
            },
        )

    def test_item_id_becomes_original_group_url(self) -> None:
        self.assertEqual(
            feed._canonical_url({"item_id": "1234567890"}),
            "https://www.toutiao.com/group/1234567890/",
        )

    def test_off_domain_fallback_url_is_rejected(self) -> None:
        self.assertEqual(
            feed._canonical_url({"display_url": "https://example.com/article/1"}),
            "",
        )

    def test_feed_rows_become_original_domain_articles(self) -> None:
        row = {
            "item_id": "1234567890",
            "title": "国产大模型发布最新推理能力",
            "abstract": "公开技术信息摘要",
            "source": "科技媒体",
            "behot_time": 1720000000,
        }
        spec = {
            "id": "track-ai-toutiao",
            "name": "AI · 今日头条",
            "categories": ["news_tech"],
            "maxItems": 4,
            "keywords": [],
        }
        with patch.object(feed, "_fetch_category", return_value=[row]):
            articles, status = feed.crawl_toutiao_source(spec, "unused", self._crawler())

        self.assertEqual(status["status"], "ok")
        self.assertEqual(len(articles), 1)
        self.assertEqual(
            articles[0]["source"]["url"],
            "https://www.toutiao.com/group/1234567890/",
        )
        self.assertEqual(articles[0]["source"]["platform"], "今日头条")


if __name__ == "__main__":
    unittest.main()
