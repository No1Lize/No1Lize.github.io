import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "person_wechat_video_discovery",
    ROOT / "tools" / "person_wechat_video_discovery.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PersonWeChatVideoDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "name": "Sam Altman",
            "englishName": "Sam Altman",
            "aliases": ["Samuel Altman"],
            "sectors": ["AI / AGI"],
            "override": {"organizationHints": ["OpenAI"]},
        }
        self.article = {
            "title": "Sam Altman 公开访谈",
            "summary": "围绕 OpenAI 的公开对话",
            "publishedAt": "2026-07-25",
            "url": "https://mp.weixin.qq.com/s/example",
            "sourceName": "科技访谈",
        }

    def test_normalizes_only_original_wechat_channel_share_urls(self):
        self.assertEqual(
            MODULE.normalize_wechat_share_url(
                "https://channels.weixin.qq.com/web/pages/feed?oid=abc&amp;scene=1"
            ),
            "https://channels.weixin.qq.com/web/pages/feed?oid=abc&scene=1",
        )
        self.assertEqual(
            MODULE.normalize_wechat_share_url("https:\\/\\/weixin.qq.com\\/sph\\/Token123"),
            "https://weixin.qq.com/sph/Token123",
        )
        self.assertEqual(MODULE.normalize_wechat_share_url("https://example.com/video"), "")
        self.assertEqual(MODULE.normalize_wechat_share_url("https://channels.weixin.qq.com/"), "")

    def test_extracts_mp_common_videosnap_original_link_and_metadata(self):
        body = """
        <mp-common-videosnap
          data-desc="Sam Altman 公开对话"
          data-nickname="科技访谈"
          data-url="https://channels.weixin.qq.com/web/pages/feed?oid=abc&amp;scene=1">
        </mp-common-videosnap>
        """
        rows = MODULE.extract_embedded_wechat_videos(body, self.article)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://channels.weixin.qq.com/web/pages/feed?oid=abc&scene=1")
        self.assertEqual(rows[0]["type"], "qa")
        self.assertEqual(rows[0]["source"], "微信视频号 · 科技访谈")

    def test_extracts_escaped_sph_share_link_from_public_article_html(self):
        body = 'window.videoShare="https:\\/\\/weixin.qq.com\\/sph\\/ShareToken";'
        rows = MODULE.extract_embedded_wechat_videos(body, self.article)
        self.assertEqual(rows[0]["url"], "https://weixin.qq.com/sph/ShareToken")
        self.assertIn("科技访谈", rows[0]["source"])

    def test_matching_articles_requires_person_identity_and_public_wechat_host(self):
        articles = [
            {
                "title": "Sam Altman 对话",
                "summary": "OpenAI",
                "publishedAt": "2026-07-25",
                "source": {"name": "公众号A", "url": "https://mp.weixin.qq.com/s/a"},
            },
            {
                "title": "Satya Nadella 对话",
                "summary": "OpenAI",
                "publishedAt": "2026-07-25",
                "source": {"name": "公众号B", "url": "https://mp.weixin.qq.com/s/b"},
            },
            {
                "title": "Sam Altman 对话",
                "summary": "OpenAI",
                "publishedAt": "2026-07-25",
                "source": {"name": "普通网站", "url": "https://example.com/a"},
            },
        ]
        rows = MODULE.matching_public_wechat_articles(self.candidate, articles)
        self.assertEqual([row["url"] for row in rows], ["https://mp.weixin.qq.com/s/a"])

    def test_public_article_failure_does_not_block_other_articles(self):
        second = {**self.article, "url": "https://mp.weixin.qq.com/s/second"}
        body = '<mp-common-videosnap data-desc="Sam Altman 访谈" data-url="https://weixin.qq.com/sph/GoodToken">'
        with patch.object(
            MODULE,
            "matching_public_wechat_articles",
            return_value=[self.article, second],
        ), patch.object(MODULE, "_sogou_articles", return_value=[]), patch.object(
            MODULE,
            "request_text",
            side_effect=[None, body],
        ):
            rows = MODULE.discover_person_wechat_video_materials(self.candidate)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["url"], "https://weixin.qq.com/sph/GoodToken")


if __name__ == "__main__":
    unittest.main()
