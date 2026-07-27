from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET
from types import SimpleNamespace
from unittest.mock import patch

from tools import search_index_feed_redirects as redirects


class SearchIndexFeedRedirectTests(unittest.TestCase):
    def setUp(self) -> None:
        redirects._CACHE.clear()

    @staticmethod
    def _crawler(parse_feed_items=None) -> SimpleNamespace:
        def xml_local(tag: str) -> str:
            return tag.rsplit("}", 1)[-1].lower()

        def xml_text(node: ET.Element, names: tuple[str, ...]) -> str:
            wanted = {name.lower() for name in names}
            for child in node.iter():
                if xml_local(child.tag) in wanted:
                    return " ".join(child.itertext()).strip()
            return ""

        return SimpleNamespace(
            DEFAULT_USER_AGENT="test-agent",
            _xml_local=xml_local,
            _xml_text=xml_text,
            clean_title=lambda value: value.strip(),
            strip_html=lambda value: value.strip(),
            _matches_keywords=lambda _title, _summary, _keywords, title_only=False: True,
            parse_feed_items=parse_feed_items,
        )

    def test_google_news_wrapper_is_rewritten_before_host_filtering(self) -> None:
        def original_parse(body: str, _spec: dict) -> list[str]:
            root = ET.fromstring(body)
            return [
                str(node.text or "")
                for node in root.iter()
                if node.tag.rsplit("}", 1)[-1].lower() == "link"
            ]

        crawler = self._crawler(original_parse)
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
        crawler = self._crawler()
        self.assertEqual(
            redirects._resolved_feed_body(
                body,
                {"url": "https://news.google.com/rss"},
                "test",
                crawler,
            ),
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

    def test_signed_parameters_are_preferred(self) -> None:
        with patch.object(
            redirects,
            "_decoding_parameters",
            return_value=("signature-value", "1720000000"),
        ), patch.object(
            redirects,
            "_post_batch",
            return_value="https://www.toutiao.com/article/123/",
        ) as post:
            resolved = redirects._batch_request("CBMtest", "test-agent")

        self.assertEqual(resolved, "https://www.toutiao.com/article/123/")
        payload = post.call_args.args[0]
        self.assertIn("signature-value", payload)
        self.assertIn("1720000000", payload)

    def test_batch_response_parser_handles_nested_json(self) -> None:
        inner = '["garturlres","https://www.toutiao.com/article/456/"]'
        response = '\n\n' + str([["wrb.fr", "Fbv4je", inner]]).replace("'", '"')
        self.assertEqual(
            redirects._parse_batch_response(response),
            "https://www.toutiao.com/article/456/",
        )


if __name__ == "__main__":
    unittest.main()
