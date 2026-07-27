from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

from tools import search_index_feed_redirects as redirects


class SearchIndexFeedRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        redirects._CACHE.clear()

    def test_google_news_wrapper_is_rewritten_before_host_filtering(self) -> None:
        def xml_local(tag: str) -> str:
            return tag.rsplit("}", 1)[-1].lower()

        def original_parse(body: str, _spec: dict) -> list[str]:
            root = ET.fromstring(body)
            return [
                str(node.text or "")
                for node in root.iter()
                if xml_local(node.tag) == "link"
            ]

        crawler = SimpleNamespace(
            DEFAULT_USER_AGENT="test-agent",
            _xml_local=xml_local,
            parse_feed_items=original_parse,
        )
        redirects.install(crawler)
        body = """<rss><channel><item>
            <title>字节跳动发布新模型</title>
            <link>https://news.google.com/rss/articles/CBMtest?oc=5</link>
            <pubDate>Mon, 27 Jul 2026 01:00:00 GMT</pubDate>
        </item></channel></rss>"""
        spec = {
            "url": "https://news.google.com/rss/search?q=site%3Atoutiao.com",
            "allowedHosts": ["toutiao.com"],
            "maxItems": 8,
        }
        with patch.object(
            redirects,
            "resolve_google_news_url",
            return_value="https://www.toutiao.com/article/1234567890/",
        ) as resolver:
            links = crawler.parse_feed_items(body, spec)

        self.assertIn("https://www.toutiao.com/article/1234567890/", links)
        resolver.assert_called_once()

    def test_unrestricted_google_feed_is_left_unchanged(self) -> None:
        body = "<rss><channel><item><link>https://news.google.com/rss/articles/abc</link></item></channel></rss>"
        crawler = SimpleNamespace(_xml_local=lambda tag: tag, DEFAULT_USER_AGENT="test")
        self.assertEqual(
            redirects._resolved_feed_body(body, {"url": "https://news.google.com/rss"}, "test", crawler),
            body,
        )

    def test_only_allowlisted_final_hosts_are_accepted(self) -> None:
        article = "https://news.google.com/rss/articles/CBMtest?oc=5"
        with patch.object(
            redirects,
            "_batch_request",
            return_value="https://example.com/not-toutiao",
        ):
            self.assertEqual(
                redirects.resolve_google_news_url(article, ["toutiao.com"], "test"),
                "",
            )

    def test_direct_toutiao_link_needs_no_resolution(self) -> None:
        direct = "https://m.toutiao.com/article/123/"
        self.assertEqual(
            redirects.resolve_google_news_url(direct, ["toutiao.com"], "test"),
            direct,
        )


if __name__ == "__main__":
    unittest.main()
