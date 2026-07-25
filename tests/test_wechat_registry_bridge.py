from __future__ import annotations

import unittest

from tools import crawl_articles
from tools import wechat_public_sources as wechat
from tools import wechat_registry_bridge as bridge


class WeChatRegistryBridgeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bridge.install(wechat)

    def test_bridge_replaces_generic_generation_with_account_registry(self) -> None:
        tracks = [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "keywords": ["大模型", "推理模型"],
                "people": ["何恺明"],
                "sampleCompanies": ["OpenAI", "DeepSeek"],
            }
        ]
        sources = wechat.generated_wechat_sources(tracks, object())
        names = {item["name"] for item in sources}
        self.assertIn("量子位", names)
        self.assertIn("机器之心", names)
        self.assertTrue(all(item.get("expectedAccounts") for item in sources))

    def test_bridge_rejects_wrong_account_before_entity_parsing(self) -> None:
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "region": "中国",
            "sourceLevel": "媒体报道",
            "keywords": ["大模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
            "expectedAccounts": ["量子位", "qbitai"],
            "accountConfigId": "qbitai",
        }
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新大模型" />
          <meta name="description" content="OpenAI发布新大模型并公布技术进展。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">无关公众号</a>
          <div id="js_content">OpenAI发布新大模型。</div>
        </body></html>
        """
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/wrong-account",
            body,
            crawl_articles,
        )
        self.assertIsNone(article)

    def test_verified_account_keeps_media_level_and_entity_links(self) -> None:
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "region": "中国",
            "sourceLevel": "媒体报道",
            "keywords": ["大模型", "推理模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": ["Sam Altman"],
            "expectedAccounts": ["量子位", "qbitai"],
            "accountConfigId": "qbitai",
        }
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型" />
          <meta name="description" content="OpenAI发布新推理模型，Sam Altman介绍后续方向。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">OpenAI发布新推理模型，Sam Altman介绍后续方向。</div>
        </body></html>
        """
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/verified-account",
            body,
            crawl_articles,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article["source"]["level"], "媒体报道")
        self.assertEqual(article["wechatAccountConfigId"], "qbitai")
        self.assertIn("OpenAI", article["mentionedCompanies"])
        self.assertIn("Sam Altman", article["mentionedPeople"])


if __name__ == "__main__":
    unittest.main()
