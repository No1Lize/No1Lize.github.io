from __future__ import annotations

import unittest

from tools import crawl_articles
from tools import crawl_with_tracking
from tools import wechat_public_sources as wechat
from tools import wechat_registry_bridge as bridge


class WeChatPublicIndexFallbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        bridge.install(wechat)

    def _qbit_spec(self) -> dict:
        tracking = crawl_with_tracking.load_tracking()
        tracks = crawl_with_tracking._enabled_tracks(tracking)
        specs = wechat.generated_wechat_sources(tracks, crawl_with_tracking)
        return next(
            spec
            for spec in specs
            if spec.get("accountConfigId") == "qbitai"
            and spec.get("sector") == "AI / AGI"
        )

    def test_registry_attaches_public_fallback_indexes(self) -> None:
        spec = self._qbit_spec()
        self.assertIn("https://weixin.imaseo.com/", spec["publicIndexUrls"])
        self.assertNotIn("_wechat", spec)

    def test_index_parser_keeps_only_matching_account_and_relevant_titles(self) -> None:
        spec = self._qbit_spec()
        body = """
        <html><body>
          <a href="https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=good">
            OpenAI发布新推理模型
          </a>
          AI 量子位 2026-07-25 04:02:00 UTC
          <a href="https://mp.weixin.qq.com/s?__biz=abc&mid=2&idx=1&sn=wrong">
            OpenAI发布另一个模型
          </a>
          AI 无关公众号 2026-07-25 04:02:00 UTC
        </body></html>
        """
        rows = bridge._extract_index_rows(
            body,
            "https://weixin.imaseo.com/",
            spec,
            crawl_articles,
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("OpenAI发布新推理模型", rows[0]["title"])
        self.assertEqual(rows[0]["date"], "2026-07-25")

    def test_empty_bing_feed_recovers_from_public_index_and_original_page(self) -> None:
        spec = self._qbit_spec()
        index_html = """
        <html><body>
          <a href="https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=verified">
            OpenAI发布新推理模型，Sam Altman介绍后续方向
          </a>
          AI 量子位 2026-07-25 04:02:00 UTC
        </body></html>
        """
        original_page = """
        <html><head>
          <meta property="og:title" content="OpenAI发布新推理模型，Sam Altman介绍后续方向" />
          <meta name="description" content="OpenAI发布新推理模型，并介绍智能体和多模态能力。" />
          <meta property="article:published_time" content="2026-07-25" />
        </head><body>
          <a id="js_name">量子位</a>
          <div id="js_content">
            OpenAI发布新推理模型。Sam Altman表示，智能体和多模态能力将持续演进。
          </div>
        </body></html>
        """
        original_fetch_text = crawl_articles.fetch_text
        original_fetch_page = wechat.fetch_public_wechat_page
        bridge._INDEX_CACHE.clear()

        def fake_fetch_text(url: str, user_agent: str, *args, **kwargs) -> str:
            if "bing.com/search" in url:
                return "<rss><channel></channel></rss>"
            if url == "https://weixin.imaseo.com/":
                return index_html
            raise AssertionError(f"unexpected index request: {url}")

        try:
            crawl_articles.fetch_text = fake_fetch_text
            wechat.fetch_public_wechat_page = lambda url, *args, **kwargs: original_page
            articles, status = wechat.crawl_wechat_source(
                spec,
                crawl_articles.DEFAULT_USER_AGENT,
                crawl_articles,
            )
        finally:
            crawl_articles.fetch_text = original_fetch_text
            wechat.fetch_public_wechat_page = original_fetch_page
            bridge._INDEX_CACHE.clear()

        self.assertEqual(status["accepted"], 1)
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["wechatAccount"], "量子位")
        self.assertEqual(articles[0]["source"]["platform"], "微信")
        self.assertIn("OpenAI", articles[0]["mentionedCompanies"])
        self.assertIn("Sam Altman", articles[0]["mentionedPeople"])


if __name__ == "__main__":
    unittest.main()
