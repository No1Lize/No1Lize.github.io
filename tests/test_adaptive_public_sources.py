from __future__ import annotations

import unittest
from urllib.parse import urlsplit

from tools import adaptive_public_sources as adaptive


class FakeCrawler:
    @staticmethod
    def normalize_url(url: str) -> str:
        return url.rstrip("/")

    @staticmethod
    def _status(
        source_id: str,
        name: str,
        status: str,
        scanned: int,
        accepted: int,
        *,
        failed: int = 0,
        platform: str = "",
        error: str | None = None,
    ) -> dict:
        result = {
            "id": source_id,
            "name": name,
            "status": status,
            "scanned": scanned,
            "accepted": accepted,
            "failed": failed,
            "platform": platform,
        }
        if error:
            result["error"] = error
        return result


class FakeGeneric:
    @staticmethod
    def platform_name(spec: dict) -> str:
        return str(spec.get("name") or urlsplit(str(spec.get("sourceUrl"))).hostname)


class FakeRobust:
    @staticmethod
    def crawl_with_second_stage(spec, _agent, _crawler, _generic):
        source_url = spec["sourceUrl"]
        if source_url == "https://tw.news.yahoo.com/":
            article = {
                "id": "yahoo-article",
                "sourceId": spec["id"],
                "title": "人工智慧新創完成融資",
                "publishedAt": "2026-07-25",
                "importance": 80,
                "source": {
                    "url": "https://tw.news.yahoo.com/ai-funding-20260725.html",
                    "name": "Yahoo奇摩",
                },
            }
            return [article], {
                "status": "ok",
                "scanned": 2,
                "accepted": 1,
                "failed": 0,
                "strategies": ["primary", "structured-data"],
            }
        return [], {
            "status": "empty",
            "scanned": 1,
            "accepted": 0,
            "failed": 0,
            "strategies": ["primary"],
        }


def article(article_id: str, url: str, day: str) -> dict:
    return {
        "id": article_id,
        "sourceId": "user-source-example",
        "title": article_id,
        "publishedAt": day,
        "importance": 70,
        "source": {"url": url, "name": "Example"},
    }


class AdaptivePublicSourceTests(unittest.TestCase):
    def test_yahoo_consent_parameters_are_removed(self) -> None:
        self.assertEqual(
            adaptive.canonical_source_url(
                "https://tw.yahoo.com/?p=us&guccounter=1&utm_source=test"
            ),
            "https://tw.yahoo.com/",
        )

    def test_unknown_site_business_parameters_are_preserved(self) -> None:
        self.assertEqual(
            adaptive.canonical_source_url(
                "https://example.com/list?p=2&from=archive&utm_source=test"
            ),
            "https://example.com/list?from=archive&p=2",
        )

    def test_unknown_deep_url_adds_root_entry(self) -> None:
        self.assertEqual(
            adaptive.source_seed_urls("https://example.com/research/archive?p=2"),
            [
                "https://example.com/research/archive?p=2",
                "https://example.com/",
            ],
        )

    def test_yahoo_profile_adds_regional_public_entries(self) -> None:
        self.assertEqual(adaptive.profile_for("https://tw.news.yahoo.com/").id, "yahoo-tw")
        self.assertEqual(
            adaptive.source_seed_urls("https://tw.yahoo.com/?p=us&guccounter=1"),
            [
                "https://tw.yahoo.com/",
                "https://tw.news.yahoo.com/",
                "https://tw.stock.yahoo.com/",
            ],
        )

    def test_eastmoney_uses_same_profile_kernel(self) -> None:
        seeds = adaptive.source_seed_urls("https://www.eastmoney.com/default.html")
        self.assertEqual(adaptive.profile_for(seeds[0]).id, "eastmoney")
        self.assertIn("https://finance.eastmoney.com/", seeds)
        self.assertIn("https://fund.eastmoney.com/", seeds)

    def test_profile_decoding_supports_big5_and_gbk(self) -> None:
        traditional = "人工智慧與半導體".encode("big5")
        simplified = "人工智能与半导体".encode("gb18030")
        self.assertEqual(
            adaptive.decode_public_bytes(traditional, "https://tw.yahoo.com/"),
            "人工智慧與半導體",
        )
        self.assertEqual(
            adaptive.decode_public_bytes(simplified, "https://finance.eastmoney.com/"),
            "人工智能与半导体",
        )

    def test_adaptive_pipeline_merges_multiple_entries(self) -> None:
        spec = {
            "id": "user-source-yahoo-tw",
            "name": "Yahoo奇摩",
            "url": "https://tw.yahoo.com/?p=us&guccounter=1",
            "sourceUrl": "https://tw.yahoo.com/?p=us&guccounter=1",
            "sourceLanguage": "",
            "maxItems": 5,
        }
        items, status = adaptive.crawl_adaptive_source(
            spec,
            "test-agent",
            FakeCrawler(),
            FakeGeneric(),
            FakeRobust(),
        )
        self.assertEqual([item["id"] for item in items], ["yahoo-article"])
        self.assertEqual(status["status"], "ok")
        self.assertEqual(status["adapter"], "adaptive-public-v1")
        self.assertEqual(status["profile"], "yahoo-tw")
        self.assertEqual(status["accepted"], 1)
        self.assertIn("structured-data", status["strategies"])
        self.assertEqual(status["canonicalSourceUrl"], "https://tw.yahoo.com/")
        self.assertEqual(status["historyLimit"], adaptive.DEFAULT_HISTORY_LIMIT)

    def test_successful_adaptive_batch_keeps_bounded_history(self) -> None:
        existing = [
            article("old-1", "https://example.com/news/old-1", "2026-07-23"),
            article("old-2", "https://example.com/news/old-2", "2026-07-24"),
        ]
        incoming = [
            article("new-1", "https://example.com/news/new-1", "2026-07-25"),
            article("new-2", "https://example.com/news/old-2", "2026-07-25"),
        ]
        status = {
            "id": "user-source-example",
            "status": "ok",
            "accepted": 2,
            "adapter": "adaptive-public-v1",
            "historyLimit": 3,
        }

        merged = adaptive.merge_adaptive_history(
            existing,
            incoming,
            [status],
            FakeCrawler(),
        )

        self.assertEqual(
            [item["id"] for item in merged],
            ["new-2", "new-1", "old-1"],
        )
        self.assertEqual(status["newAccepted"], 2)
        self.assertEqual(status["accepted"], 3)
        self.assertEqual(status["retainedPreviousCount"], 1)
        self.assertTrue(status["retainedPrevious"])

    def test_failed_adaptive_batch_does_not_replace_history(self) -> None:
        incoming = [article("other", "https://other.example/news/1", "2026-07-25")]
        status = {
            "id": "user-source-example",
            "status": "error",
            "accepted": 0,
            "adapter": "adaptive-public-v1",
        }
        self.assertEqual(
            adaptive.merge_adaptive_history([], incoming, [status], FakeCrawler()),
            incoming,
        )


if __name__ == "__main__":
    unittest.main()
