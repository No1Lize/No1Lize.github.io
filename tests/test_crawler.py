import json
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import tools.crawl_official_companies as official_companies
from tools.crawl_articles import (
    ArticleHTMLParser,
    NewsSource,
    _latest_metric,
    discover_news_urls,
    evaluate_quality,
    infer_company,
    infer_event_type,
    load_existing_payload,
    merge_articles,
    normalize_date,
    normalize_url,
    parse_feed_items,
    parse_news_article,
    parse_sina_items,
    parse_x_timeline,
    repair_media_company_attribution,
    replace_source_batches,
    sec_article,
    write_if_changed,
)
from tools.crawl_official_companies import (
    CompanySpec,
    _article_from_page,
    _discover_sitemap_urls,
    discover_candidate_urls,
    load_registry,
    replace_official_source_batches,
)


def article(identifier: str, url: str, source_id: str | None = None) -> dict:
    value = {
        "id": identifier,
        "title": identifier,
        "summary": "摘要",
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
            "platform": "官方网站",
        },
    }
    if source_id:
        value["sourceId"] = source_id
    return value


class CrawlerTests(unittest.TestCase):
    def test_normalize_url_removes_tracking_and_fragment(self) -> None:
        self.assertEqual(
            normalize_url("HTTPS://Example.com/news/?utm_source=x&b=2&a=1#section"),
            "https://example.com/news?a=1&b=2",
        )

    def test_date_validation_rejects_malformed_and_future_dates(self) -> None:
        today = datetime.now(ZoneInfo("Asia/Taipei")).date()
        self.assertIsNone(normalize_date("2026-52-26"))
        self.assertIsNone(normalize_date("January 1, 2099"))
        self.assertIsNone(normalize_date("4070908800"))
        self.assertEqual(normalize_date(today.isoformat()), today.isoformat())
        self.assertIsNone(normalize_date((today + timedelta(days=1)).isoformat()))
        self.assertEqual(normalize_date("Fri, 24 Jul 2026 08:00:00 GMT"), "2026-07-24")
        self.assertEqual(normalize_date("发布于 2026年6月17日"), "2026-06-17")
        self.assertEqual(normalize_date("2025/11/19"), "2025-11-19")

    def test_meta_without_property_or_name_does_not_crash(self) -> None:
        parser = ArticleHTMLParser()
        parser.feed('<meta charset="utf-8"><meta name="description" content="ok">')
        self.assertEqual(parser.meta["description"], "ok")

    def test_event_inference_does_not_treat_exchange_mentions_as_ipo(self) -> None:
        self.assertNotEqual(infer_event_type("Company listed on Nasdaq reports update")[0], "IPO")
        self.assertEqual(infer_event_type("Company files for IPO")[0], "IPO")
        self.assertEqual(infer_event_type("City adopts new AI regulation")[0], "政策")

    def test_media_company_inference_uses_unambiguous_title_only(self) -> None:
        self.assertEqual(
            infer_company(
                "Claude launches a new enterprise agent",
                "The market also includes ChatGPT and other assistants.",
            )[:2],
            ("Anthropic", "anthropic"),
        )
        self.assertEqual(
            infer_company(
                "AI startup raises a new funding round",
                "The company competes with DeepSeek.",
            )[:2],
            ("科技产业", None),
        )
        self.assertEqual(
            infer_company(
                "OpenAI and Anthropic publish competing benchmarks",
                "",
            )[:2],
            ("科技产业", None),
        )

    def test_existing_media_attribution_is_repaired(self) -> None:
        wrong = article(
            "wrong-company",
            "https://media.example/claude",
            "venturebeat-ai",
        )
        wrong["title"] = "Claude adds new research capabilities"
        wrong["summary"] = "The article compares the release with ChatGPT."
        wrong["company"] = "OpenAI"
        wrong["companySlug"] = "openai"
        wrong["source"]["level"] = "媒体报道"
        repaired = repair_media_company_attribution([wrong])
        self.assertEqual(repaired[0]["company"], "Anthropic")
        self.assertEqual(repaired[0]["companySlug"], "anthropic")

    def test_merge_deduplicates_by_canonical_url(self) -> None:
        old = article("curated-id", "https://example.com/item/?utm_source=old")
        new = article("generated-id", "https://example.com/item")
        merged = merge_articles([old], [new])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "curated-id")

    def test_disabled_source_removes_previous_generated_batch(self) -> None:
        existing = [
            article("old-paper", "https://example.com/paper", "openalex-ai"),
            article("old-news", "https://example.com/news", "feed-a"),
        ]
        merged = replace_source_batches(
            existing,
            [],
            [
                {
                    "id": "openalex-ai",
                    "name": "OpenAlex",
                    "status": "disabled",
                    "scanned": 0,
                    "accepted": 0,
                    "failed": 0,
                }
            ],
        )
        self.assertEqual([item["id"] for item in merged], ["old-news"])

    def test_successful_source_replaces_batch_failed_source_is_retained(self) -> None:
        existing = [
            article("old-a", "https://example.com/a", "feed-a"),
            article("old-b", "https://example.com/b", "feed-b"),
        ]
        incoming = [article("new-a", "https://example.com/new-a", "feed-a")]
        merged = replace_source_batches(
            existing,
            incoming,
            [
                {"id": "feed-a", "status": "ok", "accepted": 1},
                {"id": "feed-b", "status": "error", "accepted": 0},
            ],
        )
        self.assertEqual({item["id"] for item in merged}, {"new-a", "old-b"})

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
        listing = '<a href="/news/product-launch">Product launch</a><a href="/about">About</a>'
        self.assertEqual(
            discover_news_urls(source, listing),
            ["https://example.com/news/product-launch"],
        )
        page = """
        <html><head>
          <meta property="og:title" content="Introducing Example One | Example">
          <meta property="og:description" content="A new model for developers.">
          <meta property="article:published_time" content="2026-07-23T12:00:00Z">
        </head><body><h1>Introducing Example One</h1></body></html>
        """
        parsed = parse_news_article(source, "https://example.com/news/product-launch", page)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["publishedAt"], "2026-07-23")
        self.assertEqual(parsed["type"], "产品发布")

    def test_official_candidates_keep_index_order_when_scores_tie(self) -> None:
        listing = (
            '<a href="/news/z-last">Newest article</a>'
            '<a href="/news/a-first">Older article</a>'
            '<a href="/news/m-middle">Oldest article</a>'
        )
        candidates, _ = discover_candidate_urls(
            "https://example.com/news",
            listing,
            ("example.com",),
            2,
        )
        self.assertEqual(
            candidates,
            [
                "https://example.com/news/z-last",
                "https://example.com/news/a-first",
            ],
        )

    def test_sitemap_prioritizes_article_patterns_over_early_indexes(self) -> None:
        spec = CompanySpec(
            slug="example",
            name="Example",
            region="美国",
            sector="AI / AGI",
            homepage="https://example.com/",
            news_urls=("https://example.com/news",),
            sitemap_urls=("https://example.com/sitemap.xml",),
            aliases=(),
            entity_aliases=("Example",),
            article_url_patterns=(r"/news/[a-z0-9]+-",),
            require_entity_match=False,
            max_items=4,
            max_candidate_links=2,
            max_age_days=730,
            request_timeout=10,
        )
        sitemap = """
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
          <url><loc>https://example.com/news</loc></url>
          <url><loc>https://example.com/blog</loc></url>
          <url><loc>https://example.com/news/alpha-launch</loc></url>
          <url><loc>https://example.com/news/beta-release</loc></url>
        </urlset>
        """
        with patch.object(official_companies, "fetch_text", return_value=sitemap):
            candidates, scanned, failures = _discover_sitemap_urls(spec, "test")
        self.assertEqual(
            candidates,
            [
                "https://example.com/news/alpha-launch",
                "https://example.com/news/beta-release",
            ],
        )
        self.assertEqual((scanned, failures), (1, 0))

    def test_official_registry_must_exactly_match_company_catalog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            registry_path = root / "official.json"
            catalog_path = root / "catalog-data.ts"
            registry_path.write_text(
                json.dumps(
                    {
                        "expectedCompanyCount": 1,
                        "companies": [
                            {
                                "slug": "example",
                                "name": "Example",
                                "region": "美国",
                                "sector": "AI / AGI",
                                "homepage": "https://example.com/",
                                "newsUrls": [],
                                "aliases": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            catalog_path.write_text(
                'export const companies: Company[] = [\n'
                '  { slug:"example", name:"Example", region:"美国", '
                'sector:"AI / AGI", stage:"成长期", status:"运营中" },\n'
                "];\n",
                encoding="utf-8",
            )
            self.assertEqual(
                [spec.slug for spec in load_registry(registry_path, catalog_path)],
                ["example"],
            )
            catalog_path.write_text(
                'export const companies: Company[] = [\n'
                '  { slug:"missing", name:"Missing", region:"美国", '
                'sector:"AI / AGI", stage:"成长期", status:"运营中" },\n'
                "];\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "does not match company catalog"):
                load_registry(registry_path, catalog_path)

    def test_official_parser_rejects_indexes_and_wrong_group_company(self) -> None:
        spec = CompanySpec(
            slug="bgi-genomics",
            name="华大基因",
            region="中国",
            sector="生物科技",
            homepage="https://www.bgi.com/",
            news_urls=("https://www.bgi.com/news",),
            sitemap_urls=(),
            aliases=("BGI Genomics",),
            entity_aliases=("华大基因", "BGI Genomics"),
            article_url_patterns=(r"/news/\d+$",),
            require_entity_match=True,
            max_items=4,
            max_candidate_links=10,
            max_age_days=730,
            request_timeout=10,
        )
        listing = (
            '<a href="/news/2026072204">公司进展</a>'
            '<a href="/about">About</a>'
        )
        candidates, _ = discover_candidate_urls(
            spec.news_urls[0],
            listing,
            spec.allowed_hosts,
            spec.max_candidate_links,
            spec.article_url_patterns,
        )
        self.assertEqual(candidates, ["https://www.bgi.com/news/2026072204"])

        index_page = """
        <meta property="og:title" content="新闻中心">
        <meta property="article:published_time" content="2026-07-23">
        """
        self.assertIsNone(
            _article_from_page(spec, "https://www.bgi.com/news", index_page)
        )

        group_page = """
        <meta property="og:title" content="华大集团发布生命科学计划">
        <meta property="og:description" content="华大集团介绍集团层面的最新进展。">
        <meta property="article:published_time" content="2026-07-23">
        """
        self.assertIsNone(
            _article_from_page(
                spec, "https://www.bgi.com/news/2026072204", group_page
            )
        )

        company_page = """
        <meta property="og:title" content="华大基因发布精准医学新方案">
        <meta property="og:description" content="华大基因公布产品和业务进展。">
        <meta property="article:published_time" content="2026-07-23">
        """
        parsed = _article_from_page(
            spec, "https://www.bgi.com/news/2026072205", company_page
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["companySlug"], "bgi-genomics")

    def test_official_parser_ignores_homepage_og_url_and_reads_local_date(self) -> None:
        spec = CompanySpec(
            slug="example",
            name="Example",
            region="美国",
            sector="AI / AGI",
            homepage="https://example.com/",
            news_urls=("https://example.com/news",),
            sitemap_urls=(),
            aliases=(),
            entity_aliases=("Example",),
            article_url_patterns=(r"/news/\d+$",),
            require_entity_match=False,
            max_items=4,
            max_candidate_links=10,
            max_age_days=730,
            request_timeout=10,
        )
        page = """
        <html><head>
          <meta property="og:url" content="https://example.com/">
          <title>Example launches a new platform | Example</title>
        </head><body>
          <h1>Latest</h1>
          <h1>Example launches a new platform</h1>
          <time>2026年6月17日</time>
          <aside>最新资讯 2026年7月21日</aside>
        </body></html>
        """
        parsed = _article_from_page(
            spec,
            "https://example.com/news/322",
            page,
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["publishedAt"], "2026-06-17")
        self.assertEqual(parsed["source"]["url"], "https://example.com/news/322")

    def test_official_crawl_reports_every_registered_company(self) -> None:
        base = CompanySpec(
            slug="one",
            name="One",
            region="美国",
            sector="AI / AGI",
            homepage="https://one.example/",
            news_urls=(),
            sitemap_urls=(),
            aliases=(),
            entity_aliases=("One",),
            article_url_patterns=(),
            require_entity_match=False,
            max_items=4,
            max_candidate_links=10,
            max_age_days=730,
            request_timeout=10,
        )
        specs = [base, replace(base, slug="two", name="Two")]

        def fake_crawl(spec: CompanySpec, _user_agent: str):
            if spec.slug == "two":
                raise RuntimeError("blocked")
            return [], {
                "id": spec.source_id,
                "name": spec.name,
                "company": spec.name,
                "companySlug": spec.slug,
                "coverage": "attempted",
                "status": "empty",
                "scanned": 1,
                "accepted": 0,
                "failed": 0,
            }

        with patch.object(official_companies, "crawl_company", side_effect=fake_crawl):
            _, statuses = official_companies.crawl_all_companies(specs, "test")
        self.assertEqual(
            {status["companySlug"] for status in statuses}, {"one", "two"}
        )
        self.assertTrue(all(status["coverage"] == "attempted" for status in statuses))

    def test_completed_empty_official_batch_removes_stale_articles(self) -> None:
        stale = article(
            "stale-index",
            "https://example.com/news",
            "official-example",
        )
        retained = article(
            "temporary-failure",
            "https://other.example/news",
            "official-other",
        )
        transient_empty = article(
            "transient-empty",
            "https://third.example/news",
            "official-third",
        )
        merged = replace_official_source_batches(
            [stale, retained, transient_empty],
            [],
            [
                {
                    "id": "official-example",
                    "status": "empty",
                    "accepted": 0,
                    "failed": 0,
                },
                {"id": "official-other", "status": "error", "accepted": 0},
                {
                    "id": "official-third",
                    "status": "empty",
                    "accepted": 0,
                    "failed": 1,
                },
            ],
        )
        self.assertEqual(
            {item["id"] for item in merged},
            {"temporary-failure", "transient-empty"},
        )

    def test_rss_feed_is_filtered_and_parsed(self) -> None:
        feed = """
        <rss><channel><item><title>AI startup raises funding</title>
        <link>https://media.example/ai-round</link>
        <description>Series A for an agent company.</description>
        <pubDate>Fri, 24 Jul 2026 08:00:00 GMT</pubDate></item>
        <item><title>Critical analysis of water systems</title><link>https://media.example/water</link>
        <pubDate>Fri, 24 Jul 2026 08:00:00 GMT</pubDate></item></channel></rss>
        """
        spec = {
            "id": "media",
            "name": "Media",
            "platform": "专业媒体",
            "sourceLevel": "媒体报道",
            "region": "美国",
            "keywords": ["AI"],
        }
        parsed = parse_feed_items(feed, spec)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["type"], "融资")

    def test_sina_parser_uses_title_filter_and_valid_date(self) -> None:
        payload = json.dumps(
            {
                "result": {
                    "data": [
                        {
                            "title": "人工智能公司完成融资",
                            "url": "https://finance.sina.com.cn/tech/1.shtml",
                            "createtime": "2026-07-24",
                            "intro": "公司宣布新一轮融资。",
                        },
                        {
                            "title": "国际油价波动",
                            "url": "https://finance.sina.com.cn/market/2.shtml",
                            "createtime": "2026-07-24",
                        },
                    ]
                }
            }
        )
        spec = {
            "id": "sina",
            "name": "新浪财经",
            "platform": "新浪",
            "sourceLevel": "媒体报道",
            "region": "中国",
            "keywords": ["人工智能", "融资"],
        }
        parsed = parse_sina_items(payload, spec)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["region"], "中国")

    def test_x_public_timeline_parses_original_post(self) -> None:
        timeline = {
            "props": {
                "pageProps": {
                    "timeline": {
                        "entries": [
                            {
                                "content": {
                                    "tweet": {
                                        "conversation_id_str": "123",
                                        "created_at": "Thu Jul 23 12:00:00 +0000 2026",
                                        "full_text": "New research on reasoning agents.",
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
        body = (
            '<script id="__NEXT_DATA__" type="application/json">'
            + json.dumps(timeline)
            + "</script>"
        )
        spec = {
            "id": "x-researcher",
            "name": "Researcher",
            "kind": "person",
            "personSlug": "researcher",
            "region": "美国",
        }
        parsed = parse_x_timeline(body, spec)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["type"], "人物观点")
        self.assertEqual(parsed[0]["personSlug"], "researcher")

    def test_sec_article_and_latest_metric_are_traceable(self) -> None:
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
        facts = {
            "facts": {
                "us-gaap": {
                    "Revenues": {
                        "units": {
                            "USD": [
                                {"val": 100, "filed": "2025-03-01", "end": "2024-12-31", "form": "10-K", "accn": "old"},
                                {"val": 40, "filed": "2026-05-01", "end": "2026-03-31", "form": "10-Q", "accn": "new"},
                            ]
                        }
                    }
                }
            }
        }
        metric = _latest_metric(facts, "revenue", "营业收入", ("Revenues",))
        assert metric is not None
        self.assertEqual(metric["accessionNumber"], "new")

    def test_quality_gate_rejects_invalid_and_concentrated_snapshot(self) -> None:
        items = [article(f"a-{index}", f"https://example.com/{index}", "one") for index in range(3)]
        quality = evaluate_quality(
            items,
            [{"id": "one", "status": "ok", "accepted": 3}],
            {
                "minimumArticles": 2,
                "minimumHealthySources": 1,
                "minimumRegions": 1,
                "minimumSourceLevels": 1,
                "minimumPlatforms": 1,
                "minimumEventTypes": 1,
                "minimumChinaArticles": 0,
                "minimumUsArticles": 1,
                "maximumSingleSourceShare": 0.5,
            },
        )
        self.assertFalse(quality["passed"])
        self.assertFalse(quality["checks"]["maximumSingleSourceShare"]["passed"])

    def test_legacy_migration_and_unchanged_payload(self) -> None:
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
            output.parent.mkdir(parents=True)
            payload["schemaVersion"] = 3
            payload["qualityGate"] = {}
            output.write_text(json.dumps(payload), encoding="utf-8")
            self.assertFalse(
                write_if_changed(
                    payload["articles"],
                    payload,
                    output,
                    company_facts={},
                    source_status=[],
                    quality_gate={},
                )
            )


if __name__ == "__main__":
    unittest.main()
