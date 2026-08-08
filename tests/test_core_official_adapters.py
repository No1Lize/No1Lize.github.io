from __future__ import annotations

import unittest

from tools import core_official_adapters


class CoreOfficialAdaptersTests(unittest.TestCase):
    def test_install_adds_core_companies_without_duplicates(self) -> None:
        class NewsSource:
            def __init__(
                self,
                source_id,
                name,
                index_url,
                company,
                company_slug,
                region,
                sector,
                path_prefixes,
            ):
                self.id = source_id
                self.name = name
                self.index_url = index_url
                self.company = company
                self.company_slug = company_slug
                self.region = region
                self.sector = sector
                self.path_prefixes = path_prefixes

        class FakeCrawler:
            NEWS_SOURCES = (NewsSource("openai", "OpenAI", "", "OpenAI", "openai", "美国", "AI / AGI", ("/index/",)),)
            NewsSource = NewsSource

        core_official_adapters.install(FakeCrawler)
        first_ids = [source.id for source in FakeCrawler.NEWS_SOURCES]
        self.assertIn("deepseek", first_ids)
        self.assertIn("bytedance", first_ids)
        self.assertIn("google-deepmind", first_ids)
        self.assertIn("minimax", first_ids)
        self.assertIn("zhipu-ai", first_ids)
        self.assertIn("unitree", first_ids)
        self.assertIn("spacex", first_ids)
        self.assertIn("cerebras", first_ids)
        self.assertIn("scale-ai", first_ids)
        self.assertEqual(len(first_ids), len(set(first_ids)))

        core_official_adapters.install(FakeCrawler)
        second_ids = [source.id for source in FakeCrawler.NEWS_SOURCES]
        self.assertEqual(first_ids, second_ids)

    def test_adapter_set_keeps_core_count_bounded(self) -> None:
        self.assertGreaterEqual(len(core_official_adapters.CORE_OFFICIAL_SOURCES), 10)
        self.assertLessEqual(len(core_official_adapters.CORE_OFFICIAL_SOURCES), 16)
        self.assertTrue(
            all(row["path_prefixes"] for row in core_official_adapters.CORE_OFFICIAL_SOURCES)
        )


if __name__ == "__main__":
    unittest.main()
