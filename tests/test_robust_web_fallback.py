from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import crawl_articles as crawler
from tools import generic_web_sources as generic
from tools import robust_web_fallback as robust


class RobustWebFallbackTests(unittest.TestCase):
    def test_embedded_candidates_extract_js_video_identifiers(self) -> None:
        body = (
            '<script>var data={"videoId":"abc123def45",'
            '"canonicalUrl":"/watch?v=abc123def45"};</script>'
        )
        candidates = robust.embedded_candidates(
            "https://www.youtube.com/", body, generic
        )
        self.assertEqual(
            candidates,
            ["https://www.youtube.com/watch?v=abc123def45"],
        )

    def test_search_redirect_unwraps_direct_destination(self) -> None:
        wrapped = (
            "https://www.bing.com/ck/a?"
            "url=https%3A%2F%2Fexample.com%2Fnews%2Fai-launch"
        )
        self.assertEqual(
            robust.unwrap_search_result(wrapped),
            "https://example.com/news/ai-launch",
        )

    def test_sitemap_discovers_same_site_article_pages(self) -> None:
        sitemap = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/about</loc></url>
          <url><loc>https://example.com/news/2026/ai-chip-launch</loc><lastmod>2026-07-25</lastmod></url>
          <url><loc>https://other.example/news/2026/ai-chip-launch</loc></url>
        </urlset>
        """

        def fetch(url: str, *_args, **_kwargs) -> str:
            if url.endswith("/sitemap.xml"):
                return sitemap
            return "<urlset></urlset>"

        with patch.object(crawler, "fetch_text", side_effect=fetch):
            urls, scanned, errors = robust.sitemap_candidates(
                "https://example.com/",
                ["AI chip"],
                "test-agent",
                crawler,
                generic,
            )

        self.assertGreaterEqual(scanned, 1)
        self.assertEqual(errors, [])
        self.assertEqual(
            urls,
            ["https://example.com/news/2026/ai-chip-launch"],
        )

    def test_second_stage_recovers_js_only_youtube_video(self) -> None:
        source_url = "https://www.youtube.com/"
        video_url = "https://www.youtube.com/watch?v=abc123def45"
        search_page = '<script>{"videoId":"abc123def45"}</script>'
        video_page = """
        <html lang="en"><head>
          <meta property="og:title" content="New semiconductor AI chip architecture">
          <meta property="og:description" content="A technical discussion of inference accelerators.">
          <script type="application/ld+json">
            {"datePublished":"2026-07-25","uploadDate":"2026-07-25"}
          </script>
        </head><body><h1>New semiconductor AI chip architecture</h1></body></html>
        """
        spec = {
            "id": "user-source-youtube",
            "name": "YouTube",
            "url": source_url,
            "sourceUrl": source_url,
            "adapter": "generic_web",
            "sourceCategory": "media",
            "sourceLevel": "媒体报道",
            "region": "全球",
            "sector": "半导体",
            "keywords": ["半导体", "AI 芯片", "推理芯片"],
            "maxItems": 3,
        }

        def fetch(url: str, *_args, **_kwargs) -> str:
            if url == source_url:
                return '<html lang="en"><body></body></html>'
            if "youtube.com/results?search_query=" in url:
                return search_page
            if url == video_url:
                return video_page
            if "sitemap" in url:
                return "<urlset></urlset>"
            raise AssertionError(f"unexpected URL: {url}")

        empty_status = crawler._status(
            spec["id"], "YouTube", "empty", 2, 0, platform="YouTube"
        )
        with (
            patch.object(generic, "crawl_generic_source", return_value=([], empty_status)),
            patch.object(crawler, "fetch_text", side_effect=fetch),
        ):
            items, status = robust.crawl_with_second_stage(
                spec,
                "test-agent",
                crawler,
                generic,
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source"]["url"], video_url)
        self.assertEqual(items[0]["publishedAt"], "2026-07-25")
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["detectedLanguage"], "en")
        self.assertIn("search-page", status["strategies"])


if __name__ == "__main__":
    unittest.main()
