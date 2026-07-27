from __future__ import annotations

import unittest

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


if __name__ == "__main__":
    unittest.main()
