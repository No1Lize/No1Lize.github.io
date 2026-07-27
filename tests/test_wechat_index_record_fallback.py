from __future__ import annotations

import unittest

from tools import crawl_articles
from tools import wechat_index_record_fallback as fallback
from tools import wechat_public_sources as wechat


class WeChatIndexRecordFallbackTest(unittest.TestCase):
    def test_index_proxy_never_becomes_a_homepage_article(self) -> None:
        spec = {
            "id": "user-track-wechat-icbank-semiconductor",
            "name": "半导体行业观察",
            "sector": "半导体",
            "keywords": ["芯片", "先进封装", "HBM"],
            "trackedCompanies": ["英伟达", "台积电", "中芯国际"],
            "trackedPeople": ["黄仁勋"],
            "accountConfigId": "icbank",
        }
        row = {
            "title": "英伟达豪掷100亿，锁定先进封装",
            "summary": "半导体行业观察 公众号 半导体 9小时前",
            "url": "https://www.jintiankansha.com/t/example",
            "date": "",
            "kind": "detail",
        }
        self.assertIsNone(
            fallback._build_index_article(row, spec, crawl_articles, wechat)
        )


if __name__ == "__main__":
    unittest.main()
