import json
import tempfile
import unittest
from pathlib import Path

from tools.crawl_articles import (
    NewsSource,
    _latest_metric,
    discover_news_urls,
    load_existing_payload,
    merge_articles,
    normalize_url,
    parse_news_article,
    sec_article,
    write_if_changed,
)


def article(identifier: str, url: str, summary: str = "摘要") -> dict:
    return {
        "id": identifier,
        "title": identifier,
        "summary": summary,
        "type": "技术突破",
        "region": "美国",
        "sector": "AI / AGI",
        "company": "Example",
        "companySlug": "example",
        "publishedAt": "2026-07-24",
        "importance": 80,
        "source": {
            "name": "Example",
            "url": url,
            "level": "官方披露",
        },
    }


class CrawlerTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_and_fragment(self) -> None:
        self.assertEqual(
            normalize_url(
                "HTTPS://Example.com/news/?utm_source=x&b=2&a=1#section"
            ),
            "https://example.com/news?a=1&b=2",
        )

    def test_merge_deduplicates_by_canonical_url(self) -> None:
        old = article("curated-id", "https://example.com/item/?utm_source=old")
        new = article("generated-id", "https://example.com/item")
        merged = merge_articles([old], [new])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "curated-id")

    def test_sec_article_is_traceable(self) -> None:
        item = sec_article(
            cik="0001824920",
            company="IonQ",
            company_slug="ionq",
            sector="量子计算",
            form="10-K",
            filing_date="2026-03-01",
            accession_number="000000-26-000001",
            primary_document="ionq-10k.htm",
        )
        self.assertEqual(item["type"], "财报")
        self.assertIn("sec.gov/Archives/edgar/data/", item["source"]["url"])

    def test_official_news_page_is_discovered_and_parsed(self) -> None:
        source = NewsSource(
            "example",
            "Example Newsroom",
            "https://example.com/news",
            "Example",
            "example",
            "美国",
            "AI / AGI",
            ("/news/",),
        )
        listing = """
        <a href="/news/product-launch">Product launch</a>
        <a href="/about">About</a>
        """
        self.assertEqual(
            discover_news_urls(source, listing),
            ["https://example.com/news/product-launch"],
        )
        page = """
        <html><head>
          <meta property="og:title" content="Introducing Example One">
          <meta property="og:description" content="A new model for developers.">
          <meta property="article:published_time" content="2026-07-23T12:00:00Z">
        </head><body><h1>Introducing Example One</h1></body></html>
        """
        parsed = parse_news_article(
            source, "https://example.com/news/product-launch", page
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["publishedAt"], "2026-07-23")
        self.assertEqual(parsed["type"], "产品发布")

    def test_latest_financial_metric_keeps_period_and_filing(self) -> None:
        facts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {
                                    "val": 100,
                                    "filed": "2025-03-01",
                                    "end": "2024-12-31",
                                    "form": "10-K",
                                    "fy": 2024,
                                    "fp": "FY",
                                    "accn": "old",
                                },
                                {
                                    "val": 40,
                                    "filed": "2026-05-01",
                                    "end": "2026-03-31",
                                    "form": "10-Q",
                                    "fy": 2026,
                                    "fp": "Q1",
                                    "accn": "new",
                                },
                            ]
                        }
                    }
                }
            }
        }
        metric = _latest_metric(facts, "revenue", "营业收入", ("Revenues",))
        self.assertIsNotNone(metric)
        assert metric is not None
        self.assertEqual(metric["value"], 40)
        self.assertEqual(metric["periodEnd"], "2026-03-31")
        self.assertEqual(metric["accessionNumber"], "new")

    def test_legacy_snapshot_migrates_to_public_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "public" / "data" / "articles.json"
            legacy = root / "data" / "public" / "dashboard.json"
            legacy.parent.mkdir(parents=True)
            legacy.write_text(
                json.dumps({"updated_at": "2026-07-24", "events": [article("a", "https://example.com/a")]}),
                encoding="utf-8",
            )
            payload = load_existing_payload(output, legacy)
            self.assertEqual(payload["articleCount"], 1)
            self.assertEqual(payload["articles"][0]["id"], "a")
            self.assertEqual(payload["schemaVersion"], 2)

    def test_unchanged_payload_does_not_rewrite_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "articles.json"
            items = [article("a", "https://example.com/a")]
            payload = {
                "schemaVersion": 2,
                "generatedAt": "2026-07-24T00:00:00+00:00",
                "articleCount": 1,
                "articles": items,
                "companyFacts": {},
                "sourceStatus": [],
            }
            output.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(write_if_changed(items, payload, output))


if __name__ == "__main__":
    unittest.main()
