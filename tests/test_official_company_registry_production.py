from __future__ import annotations

import unittest

from tools import crawl_official_with_source_categories as category_crawler
from tools.crawl_official_companies import load_registry


class ProductionOfficialCompanyRegistryTests(unittest.TestCase):
    def test_registry_matches_catalog_and_contains_google(self) -> None:
        specs = load_registry()
        by_slug = {spec.slug: spec for spec in specs}
        self.assertIn("google", by_slug)
        self.assertEqual(by_slug["google"].name, "Google")
        self.assertEqual(by_slug["google"].region, "美国")
        self.assertEqual(by_slug["google"].sector, "AI / AGI")
        self.assertIn("blog.google", by_slug["google"].allowed_hosts)

    def test_precise_company_regions_map_to_public_article_contract(self) -> None:
        specs = load_registry()
        by_slug = {spec.slug: spec for spec in specs}
        self.assertEqual(by_slug["shopify"].region, "加拿大")
        self.assertEqual(category_crawler._public_article_region("中国"), "中国")
        self.assertEqual(category_crawler._public_article_region("美国"), "美国")
        self.assertEqual(category_crawler._public_article_region("全球"), "全球")
        self.assertEqual(category_crawler._public_article_region("加拿大"), "全球")

    def test_official_article_adapter_normalizes_before_quality_validation(self) -> None:
        official = category_crawler.official_tracking.official
        original = official._article_from_page

        def article_from_page(_spec, _url: str, _body: str):
            return {"region": "加拿大", "title": "Shopify official update"}

        try:
            official._article_from_page = article_from_page
            category_crawler.install_public_region_adapter()
            article = official._article_from_page(None, "https://example.com", "")
            self.assertIsNotNone(article)
            self.assertEqual(article["region"], "全球")
            self.assertEqual(article["title"], "Shopify official update")
        finally:
            official._article_from_page = original


if __name__ == "__main__":
    unittest.main()
