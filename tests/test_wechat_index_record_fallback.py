from __future__ import annotations

import unittest

from tools import crawl_articles
from tools import wechat_index_record_fallback as fallback
from tools import wechat_public_sources as wechat


class WeChatIndexRecordFallbackTest(unittest.TestCase):
    def setUp(self) -> None:
        self.spec = {
            "id": "user-track-wechat-icbank-semiconductor",
            "name": "半导体行业观察",
            "sector": "半导体",
            "region": "中国",
            "keywords": ["芯片", "先进封装", "HBM"],
            "trackedCompanies": ["英伟达", "台积电", "中芯国际"],
            "trackedPeople": ["黄仁勋"],
            "accountConfigId": "icbank",
        }

    def test_index_record_is_explicitly_marked_as_metadata_only(self) -> None:
        row = {
            "title": "英伟达豪掷100亿，锁定先进封装",
            "summary": "半导体行业观察 公众号 半导体 9小时前",
            "url": "https://www.jintiankansha.com/t/example",
            "date": "",
            "kind": "detail",
        }
        article = fallback._build_index_article(
            row,
            self.spec,
            crawl_articles,
            wechat,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article["source"]["level"], "数据库记录")
        self.assertEqual(article["source"]["platform"], "微信公开索引")
        self.assertEqual(article["wechatContentMode"], "index-only")
        self.assertEqual(article["wechatAccount"], "半导体行业观察")
        self.assertIn("英伟达", article["mentionedCompanies"])
        self.assertIn("正文将在后续成功读取微信原文时补全", article["summary"])
        self.assertEqual(article["qualityStatus"], "待交叉验证")

    def test_relative_index_dates_are_normalized(self) -> None:
        today = fallback.datetime.now(fallback.UTC).date()
        self.assertEqual(
            fallback._relative_date("3小时前", crawl_articles),
            today.isoformat(),
        )
        self.assertEqual(
            fallback._relative_date("昨天", crawl_articles),
            (today - fallback.timedelta(days=1)).isoformat(),
        )
        self.assertEqual(
            fallback._relative_date("2周前", crawl_articles),
            (today - fallback.timedelta(days=14)).isoformat(),
        )


if __name__ == "__main__":
    unittest.main()
