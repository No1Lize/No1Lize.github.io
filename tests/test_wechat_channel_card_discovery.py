import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wechat_channel_card_discovery",
    ROOT / "tools" / "wechat_channel_card_discovery.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class WeChatChannelCardDiscoveryTest(unittest.TestCase):
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

    def test_parser_extracts_only_original_share_links(self):
        body = r'''
        <section id="js_content">
          <mp-common-videosnap class="js_uneditable"
             data-title="Sam Altman 公开对话"
             data-desc="OpenAI 与 ChatGPT"
             data-nickname="测试视频号"
             data-url="https%3A%2F%2Fchannels.weixin.qq.com%2Fweb%2Fpages%2Ffeed%3Fid%3Dabc%26scene%3D1">
             <a href="https:\/\/weixin.qq.com\/sph\/A1b2C3?from=article&amp;scene=1">播放</a>
             <a href="https://mp.weixin.qq.com/s/not-a-video">公众号文章</a>
          </mp-common-videosnap>
        </section>
        '''
        rows = MODULE.extract_videosnap_cards(
            body,
            article_title="Sam Altman 访谈全文",
            article_summary="OpenAI 对话",
            article_date="2026-07-25",
            article_source="测试公众号",
        )
        self.assertEqual(
            {row["url"] for row in rows},
            {
                "https://channels.weixin.qq.com/web/pages/feed?id=abc&scene=1",
                "https://weixin.qq.com/sph/A1b2C3?from=article&scene=1",
            },
        )
        self.assertTrue(
            all(row["source"] == "微信视频号 · 测试视频号" for row in rows)
        )

    def test_discovery_uses_snapshot_and_sogou_articles(self):
        articles = [
            {
                "title": "Sam Altman 公开对话",
                "summary": "OpenAI 创始人访谈",
                "publishedAt": "2026-07-25",
                "source": {
                    "name": "站内公众号",
                    "platform": "微信",
                    "url": "https://mp.weixin.qq.com/s/local",
                },
                "mentionedPeople": ["Sam Altman"],
            }
        ]
        sogou_rows = [
            {
                "title": "Sam Altman 主题演讲",
                "summary": "OpenAI keynote",
                "publishedAt": "2026-07-24",
                "account": "索引公众号",
                "url": "https://mp.weixin.qq.com/s/sogou",
            }
        ]
        bodies = {
            "https://mp.weixin.qq.com/s/local": '<mp-common-videosnap data-title="Sam Altman 访谈" data-desc="OpenAI 对话" data-url="https://channels.weixin.qq.com/a"></mp-common-videosnap>',
            "https://mp.weixin.qq.com/s/sogou": '<mp-common-videosnap data-title="Sam Altman 演讲" data-desc="OpenAI keynote" data-url="https://weixin.qq.com/sph/b"></mp-common-videosnap>',
        }

        def fetcher(url, headers=None):
            self.assertEqual(headers["Referer"], "https://mp.weixin.qq.com/")
            return bodies[url]

        rows = MODULE.discover_embedded_wechat_video_materials(
            self.candidate,
            articles,
            article_discoverer=lambda candidate: sogou_rows,
            fetcher=fetcher,
        )
        self.assertEqual(
            {row["url"] for row in rows},
            {"https://channels.weixin.qq.com/a", "https://weixin.qq.com/sph/b"},
        )
        self.assertEqual({row["type"] for row in rows}, {"interview", "speech"})

    def test_wrong_person_and_non_original_links_are_rejected(self):
        articles = [
            {
                "title": "Sam Altman 访谈",
                "summary": "OpenAI",
                "publishedAt": "2026-07-25",
                "source": {
                    "name": "测试公众号",
                    "url": "https://mp.weixin.qq.com/s/local",
                },
            }
        ]
        body = '''
        <mp-common-videosnap data-title="Satya Nadella 访谈" data-desc="Microsoft"
          data-url="https://channels.weixin.qq.com/wrong"></mp-common-videosnap>
        <mp-common-videosnap data-title="Sam Altman 访谈" data-desc="OpenAI"
          data-url="https://example.com/not-original"></mp-common-videosnap>
        '''
        rows = MODULE.discover_embedded_wechat_video_materials(
            self.candidate,
            articles,
            article_discoverer=lambda candidate: [],
            fetcher=lambda url, headers=None: body,
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
