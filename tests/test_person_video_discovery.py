import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "person_video_discovery", ROOT / "tools" / "person_video_discovery.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PersonVideoDiscoveryTest(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "name": "Sam Altman",
            "englishName": "Sam Altman",
            "aliases": ["Samuel Altman"],
            "sectors": ["AI / AGI"],
            "override": {
                "roleHint": "OpenAI 首席执行官",
                "organizationHints": ["OpenAI"],
                "productHints": ["ChatGPT"],
            },
        }

    def test_youtube_parser_reads_public_video_renderers(self):
        payload = {
            "contents": [{
                "videoRenderer": {
                    "videoId": "abcDEF12345",
                    "title": {"runs": [{"text": "Sam Altman interview on AI"}]},
                    "ownerText": {"runs": [{"text": "Example Channel"}]},
                    "publishedTimeText": {"simpleText": "2 days ago"},
                    "descriptionSnippet": {"runs": [{"text": "OpenAI conversation"}]},
                }
            }]
        }
        page = f"<script>var ytInitialData = {json.dumps(payload)};</script>"
        with patch.object(MODULE, "request_text", return_value=page):
            rows = MODULE.discover_youtube("Sam Altman OpenAI")
        self.assertEqual(rows[0]["url"], "https://www.youtube.com/watch?v=abcDEF12345")
        self.assertEqual(rows[0]["source"], "YouTube · Example Channel")

    def test_bilibili_parser_uses_original_video_page(self):
        payload = {
            "code": 0,
            "data": {
                "result": [{
                    "bvid": "BV1abc123456",
                    "title": "<em class=\"keyword\">Sam Altman</em> 访谈",
                    "description": "OpenAI 对话",
                    "author": "科技频道",
                    "pubdate": 1760000000,
                }]
            },
        }
        with patch.object(MODULE, "request_json", return_value=payload):
            rows = MODULE.discover_bilibili("Sam Altman OpenAI")
        self.assertEqual(rows[0]["url"], "https://www.bilibili.com/video/BV1abc123456")
        self.assertEqual(rows[0]["title"], "Sam Altman 访谈")

    def test_wechat_channels_accepts_only_original_share_pages(self):
        rss = """<rss><channel>
        <item><title>Sam Altman 对话</title><link>https://channels.weixin.qq.com/platform/post/abc</link><description>OpenAI 访谈</description><pubDate>Fri, 25 Jul 2026 12:00:00 GMT</pubDate></item>
        <item><title>聚合页</title><link>https://example.com/video</link><description>Sam Altman 采访</description></item>
        <item><title>普通微信页</title><link>https://weixin.qq.com/about</link><description>Sam Altman 对话</description></item>
        </channel></rss>"""
        with patch.object(MODULE, "request_text", return_value=rss):
            rows = MODULE.discover_wechat_channels("Sam Altman OpenAI")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "微信视频号")

    def test_identity_filter_rejects_wrong_people_and_classifies_materials(self):
        rows = MODULE.discover_person_video_materials(
            self.candidate,
            discoverers={
                "YouTube": lambda query: [
                    {"title": "Sam Altman interview on AI", "description": "OpenAI", "date": "2026-07-25", "url": "https://www.youtube.com/watch?v=one1111", "source": "YouTube"},
                    {"title": "Satya Nadella interview", "description": "OpenAI", "date": "2026-07-25", "url": "https://www.youtube.com/watch?v=two2222", "source": "YouTube"},
                ],
                "Bilibili": lambda query: [
                    {"title": "Sam Altman 主题演讲", "description": "ChatGPT", "date": "2026-07-24", "url": "https://www.bilibili.com/video/BV1test", "source": "Bilibili"},
                ],
            },
        )
        self.assertEqual({item["type"] for item in rows}, {"interview", "speech"})
        self.assertFalse(any("Satya" in item["title"] for item in rows))

    def test_platform_failure_does_not_remove_other_results(self):
        def blocked(query):
            raise RuntimeError("blocked")

        rows = MODULE.discover_person_video_materials(
            self.candidate,
            discoverers={
                "YouTube": blocked,
                "Bilibili": lambda query: [{"title": "Sam Altman 访谈", "description": "OpenAI", "date": "2026-07-25", "url": "https://www.bilibili.com/video/BV1ok", "source": "Bilibili"}],
            },
        )
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
