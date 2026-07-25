import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "crawl_wechat_sources", ROOT / "tools" / "crawl_wechat_sources.py"
)
assert SPEC and SPEC.loader
wechat = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = wechat
SPEC.loader.exec_module(wechat)


class WeChatSourceTests(unittest.TestCase):
    def setUp(self):
        self.account = {
            "id": "qbitai",
            "name": "量子位",
            "region": "中国",
            "sourceLevel": "媒体报道",
            "defaultSector": "AI / AGI",
            "maxArticleAgeDays": 3650,
            "sectorKeywords": {
                "AI / AGI": ["大模型", "智能体", "推理模型"],
                "机器人": ["人形机器人", "具身智能"],
            },
            "companies": ["OpenAI", "Anthropic"],
            "people": ["Sam Altman", "何恺明"],
        }
        self.tracking = {
            "ai / agi": {
                "keywords": ["多模态"],
                "companies": ["DeepSeek"],
                "people": ["姚顺雨"],
            },
            "机器人": {
                "keywords": ["VLA"],
                "companies": ["Figure AI"],
                "people": ["王兴兴"],
            },
        }

    def test_parses_verified_account_and_links_entities(self):
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型，Sam Altman解释长期智能体方向" />
          <meta property="og:url" content="https://mp.weixin.qq.com/s/example" />
          <meta name="author" content="量子位" />
          <meta name="description" content="OpenAI公布新推理模型，并讨论长期智能体和多模态能力。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body><div id="js_content">
          OpenAI发布新推理模型。Sam Altman表示，长期智能体将继续提升多模态能力。
        </div></body></html>
        """
        article = wechat.parse_wechat_page(
            body,
            "https://mp.weixin.qq.com/s/example",
            self.account,
            "2026-07-25",
            self.tracking,
        )
        self.assertIsNotNone(article)
        assert article
        self.assertEqual(article["sector"], "AI / AGI")
        self.assertEqual(article["company"], "OpenAI")
        self.assertIn("OpenAI", article["mentionedCompanies"])
        self.assertIn("Sam Altman", article["mentionedPeople"])
        self.assertEqual(article["source"]["platform"], "微信")
        self.assertEqual(article["wechatAccount"], "量子位")

    def test_rejects_article_from_another_public_account(self):
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新模型" />
          <meta name="author" content="无关公众号" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body><div id="js_content">OpenAI发布新模型。</div></body></html>
        """
        article = wechat.parse_wechat_page(
            body,
            "https://mp.weixin.qq.com/s/other",
            self.account,
            "2026-07-25",
            self.tracking,
        )
        self.assertIsNone(article)

    def test_selects_robotics_only_when_robotics_evidence_is_stronger(self):
        text = "Figure AI发布人形机器人，具身智能和VLA能力用于机器人量产。"
        self.assertEqual(
            wechat.choose_sector(self.account, text, self.tracking),
            "机器人",
        )

    def test_empty_refresh_retains_previous_account_articles(self):
        old_article = {
            "id": "wechat-qbitai-old",
            "sourceId": "wechat-qbitai",
            "title": "旧文章",
            "publishedAt": "2026-07-20",
            "importance": 70,
            "source": {
                "name": "量子位",
                "url": "https://mp.weixin.qq.com/s/old",
                "level": "媒体报道",
                "platform": "微信",
            },
        }
        payload = {
            "schemaVersion": 3,
            "articles": [old_article],
            "sourceStatus": [],
        }
        result = wechat.merge_snapshot(
            payload,
            [],
            [
                {
                    "id": "wechat-qbitai",
                    "name": "量子位",
                    "platform": "微信",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 0,
                    "retainedPrevious": True,
                }
            ],
            {"wechat-qbitai"},
        )
        self.assertEqual(result["articleCount"], 1)
        self.assertEqual(result["articles"][0]["id"], "wechat-qbitai-old")

    def test_index_query_is_restricted_to_wechat_article_pages(self):
        url = wechat.build_index_url(self.account, self.tracking)
        self.assertIn("bing.com/search", url)
        self.assertIn("format=rss", url)
        self.assertIn("site%3Amp.weixin.qq.com", url)


if __name__ == "__main__":
    unittest.main()
