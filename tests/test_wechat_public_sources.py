from __future__ import annotations

import unittest

from tools import crawl_articles
from tools import wechat_public_sources as wechat


class WeChatPublicSourcesTest(unittest.TestCase):
    def test_generates_one_independent_query_per_track(self) -> None:
        tracks = [
            {
                "slug": "space",
                "name": "商业航天",
                "keywords": ["可复用火箭", "卫星互联网"],
                "people": ["埃隆·马斯克 @elonmusk"],
                "sampleCompanies": ["SpaceX", "Rocket Lab"],
            },
            {
                "slug": "biotech",
                "name": "生物科技",
                "keywords": ["蛋白质设计", "基因编辑"],
                "people": [],
                "sampleCompanies": ["Recursion Pharmaceuticals"],
            },
        ]
        sources = wechat.generated_wechat_sources(tracks, object())
        self.assertEqual(len(sources), 2)
        self.assertEqual(sources[0]["adapter"], "wechat_search")
        self.assertEqual(sources[0]["sector"], "商业航天")
        self.assertIn("mp.weixin.qq.com", sources[0]["url"])
        self.assertIn("SpaceX", sources[0]["trackedCompanies"])
        self.assertIn("埃隆·马斯克", sources[0]["trackedPeople"])
        self.assertNotIn("Recursion Pharmaceuticals", sources[0]["url"])

    def test_parses_public_article_summary_account_author_and_entities(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="SpaceX公布星舰商业发射计划" />
          <meta name="description" content="SpaceX公布新一轮星舰测试和商业发射安排。" />
          <meta property="article:published_time" content="2026-07-25T08:00:00+08:00" />
        </head><body>
          <a id="js_name">航天前沿</a>
          <span id="js_author_name">张航</span>
          <div id="js_content">
            <p>SpaceX公布新一轮星舰测试和商业发射安排。</p>
            <p>埃隆·马斯克表示，Starship将继续推进可复用火箭验证。</p>
          </div>
        </body></html>
        """
        spec = {
            "id": "user-track-wechat-space",
            "name": "微信公众号 · 商业航天",
            "sector": "商业航天",
            "region": "中国",
            "keywords": ["可复用火箭", "卫星互联网"],
            "trackedCompanies": ["SpaceX", "Rocket Lab"],
            "trackedPeople": ["埃隆·马斯克", "SpaceX"],
            "sourceLevel": "原始材料",
            "platform": "微信",
        }
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/example",
            html,
            crawl_articles,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertEqual(article["title"], "SpaceX公布星舰商业发射计划")
        self.assertEqual(article["publishedAt"], "2026-07-25")
        self.assertEqual(article["sector"], "商业航天")
        self.assertEqual(article["company"], "SpaceX")
        self.assertEqual(article["wechatAccount"], "航天前沿")
        self.assertEqual(article["authors"], ["张航"])
        self.assertIn("SpaceX", article["mentionedCompanies"])
        self.assertIn("埃隆·马斯克", article["mentionedPeople"])
        self.assertNotIn("SpaceX", article["mentionedPeople"])
        self.assertEqual(article["source"]["platform"], "微信")
        self.assertLessEqual(len(article["summary"]), 500)

    def test_rejects_cross_sector_or_generic_article(self) -> None:
        html = """
        <html><head>
          <meta property="og:title" content="城市生活方式观察" />
          <meta name="description" content="一篇与科技投资无关的城市生活文章。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">城市观察</a>
          <div id="js_content"><p>旅游、美食和城市生活方式。</p></div>
        </body></html>
        """
        spec = {
            "id": "user-track-wechat-energy",
            "name": "微信公众号 · 新能源",
            "sector": "新能源",
            "region": "中国",
            "keywords": ["固态电池", "储能系统"],
            "trackedCompanies": ["宁德时代"],
            "trackedPeople": [],
        }
        self.assertIsNone(
            wechat.parse_wechat_article(
                spec,
                "https://mp.weixin.qq.com/s/irrelevant",
                html,
                crawl_articles,
            )
        )

    def test_parses_unix_publish_timestamp(self) -> None:
        html = """
        <html><head><meta property="og:title" content="宁德时代发布固态电池进展" /></head>
        <body>
          <script>var ct = "1784937600";</script>
          <a id="js_name">电池产业观察</a>
          <div id="js_content"><p>宁德时代发布固态电池研发和量产进展。</p></div>
        </body></html>
        """
        spec = {
            "id": "user-track-wechat-energy",
            "name": "微信公众号 · 新能源",
            "sector": "新能源",
            "region": "中国",
            "keywords": ["固态电池"],
            "trackedCompanies": ["宁德时代"],
            "trackedPeople": [],
        }
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s/energy",
            html,
            crawl_articles,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertRegex(article["publishedAt"], r"^\d{4}-\d{2}-\d{2}$")

    def test_discovers_contextual_people_not_preconfigured(self) -> None:
        body = """
        <html><head>
          <meta property="og:title" content="OpenAI首席未来学家Joshua Achiam宣布离职" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">
            <p>OpenAI首席未来学家 Joshua Achiam 在X上宣布离职。</p>
            <p>研究员 Noam Brown 表示这一变化值得关注。</p>
            <p>论文第一作者 黄佳诺 介绍了新的推理模型。</p>
          </div>
        </body></html>
        """
        spec = {
            "id": "user-track-wechat-qbitai-ai",
            "name": "量子位",
            "sector": "AI / AGI",
            "region": "中国",
            "keywords": ["推理模型"],
            "trackedCompanies": ["OpenAI"],
            "trackedPeople": [],
            "sourceLevel": "媒体报道",
        }
        article = wechat.parse_wechat_article(
            spec,
            "https://mp.weixin.qq.com/s?__biz=test&mid=1",
            body,
            crawl_articles,
        )
        self.assertIsNotNone(article)
        assert article is not None
        self.assertIn("Joshua Achiam", article["mentionedPeople"])
        self.assertIn("Noam Brown", article["mentionedPeople"])
        self.assertIn("黄佳诺", article["mentionedPeople"])
        self.assertIn("OpenAI", article["mentionedCompanies"])
        self.assertNotIn("OpenAI", article["mentionedPeople"])


if __name__ == "__main__":
    unittest.main()
