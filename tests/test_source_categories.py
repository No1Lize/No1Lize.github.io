from __future__ import annotations

import unittest

from tools import crawl_with_source_categories as categories
from tools import migrate_article_entities as migration


class SourceCategoryRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracks = [
            {
                "slug": "ai",
                "name": "AI / AGI",
                "keywords": ["推理模型"],
                "people": [],
                "sampleCompanies": ["OpenAI"],
            }
        ]

    def test_legacy_sources_default_to_media_without_company_signals(self) -> None:
        self.assertEqual(
            categories.source_category(
                {
                    "name": "投资界",
                    "sourceType": "listing-search",
                    "company": "投资界",
                }
            ),
            "media",
        )

    def test_legacy_sec_and_ticker_sources_default_to_company(self) -> None:
        self.assertEqual(
            categories.source_category(
                {"name": "NVIDIA SEC", "sourceType": "sec", "ticker": "NVDA"}
            ),
            "company",
        )
        self.assertEqual(
            categories.source_category(
                {"name": "NVIDIA IR", "sourceType": "listing-search", "ticker": "NVDA"}
            ),
            "company",
        )

    def test_media_source_never_emits_company_entity(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "source-investment-news",
                    "name": "投资界",
                    "url": "https://www.pedaily.cn/",
                    "sourceType": "listing-search",
                    "sourceCategory": "media",
                    "region": "中国",
                    "sector": "AI / AGI",
                    "company": "投资界",
                    "ticker": "",
                    "keywords": ["AI 创业"],
                    "enabled": True,
                }
            ]
        }

        feeds, sec = categories._custom_sources(tracking, self.tracks)

        self.assertEqual(sec, {})
        self.assertEqual(len(feeds), 1)
        self.assertEqual(feeds[0]["sourceCategory"], "media")
        self.assertEqual(feeds[0]["adapter"], "generic_web")
        self.assertEqual(feeds[0]["platform"], "投资界")
        self.assertEqual(feeds[0]["sourceUrl"], "https://www.pedaily.cn/")
        self.assertNotIn("company", feeds[0])
        self.assertNotIn("companySlug", feeds[0])

    def test_person_source_never_emits_company_entity(self) -> None:
        tracking = {
            "sources": [
                {
                    "id": "source-person-blog",
                    "name": "Andrej Karpathy Blog",
                    "url": "https://karpathy.ai/",
                    "sourceType": "listing-search",
                    "sourceCategory": "person",
                    "region": "美国",
                    "sector": "AI / AGI",
                    "company": "",
                    "ticker": "",
                    "keywords": ["neural networks"],
                    "enabled": True,
                }
            ]
        }

        feeds, sec = categories._custom_sources(tracking, self.tracks)

        self.assertEqual(sec, {})
        self.assertEqual(feeds[0]["sourceCategory"], "person")
        self.assertEqual(feeds[0]["adapter"], "generic_web")
        self.assertEqual(feeds[0]["platform"], "Andrej Karpathy Blog")
        self.assertNotIn("company", feeds[0])
        self.assertNotIn("companySlug", feeds[0])

    def test_company_source_keeps_catalog_slug(self) -> None:
        tracking = {
            "listedCompanies": [
                {
                    "id": "catalog-nvidia",
                    "name": "英伟达",
                    "ticker": "NVDA",
                    "catalogSlug": "nvidia",
                }
            ],
            "sources": [
                {
                    "id": "listed-source-catalog-nvidia",
                    "name": "英伟达公告披露",
                    "url": "https://www.sec.gov/edgar/search/",
                    "sourceType": "sec",
                    "sourceCategory": "company",
                    "region": "美国",
                    "sector": "AI / AGI",
                    "company": "英伟达",
                    "ticker": "NVDA",
                    "keywords": ["英伟达", "NVDA"],
                    "enabled": True,
                    "listedCompanyId": "catalog-nvidia",
                }
            ],
        }

        feeds, sec = categories._custom_sources(tracking, self.tracks)

        self.assertEqual(feeds, [])
        self.assertEqual(sec["NVDA"], ("英伟达", "nvidia", "AI / AGI", "美国"))


class LegacyEntityMigrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracking = {
            "sources": [
                {
                    "id": "source-track-rcvvao",
                    "name": "投资界",
                    "url": "https://www.pedaily.cn/",
                    "sourceType": "listing-search",
                    "sourceCategory": "media",
                    "company": "",
                }
            ]
        }

    def test_migration_removes_profile_pages_and_fake_company_links(self) -> None:
        payload = {
            "articleCount": 3,
            "articles": [
                {
                    "id": "profile",
                    "sourceId": "official-user-投资界",
                    "title": "侃见财经的文章_投资界",
                    "company": "投资界",
                    "companySlug": "user-投资界",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/media/m899",
                        "level": "官方披露",
                    },
                },
                {
                    "id": "fake-company",
                    "sourceId": "official-user-投资界",
                    "title": "人工智能融资观察",
                    "company": "投资界",
                    "companySlug": "user-投资界",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/202607/123.shtml",
                        "level": "官方披露",
                    },
                },
                {
                    "id": "real-company",
                    "sourceId": "official-user-投资界",
                    "title": "Anthropic完成新融资",
                    "company": "Anthropic",
                    "companySlug": "anthropic",
                    "source": {
                        "name": "投资界",
                        "url": "https://www.pedaily.cn/202607/456.shtml",
                        "level": "媒体报道",
                    },
                },
            ],
            "sourceStatus": [{"id": "official-user-投资界", "status": "ok"}],
        }

        migrated, report = migration.migrate(payload, self.tracking)

        self.assertEqual(migrated["articleCount"], 2)
        self.assertEqual(report["removedNonArticles"], 1)
        cleaned = next(item for item in migrated["articles"] if item["id"] == "fake-company")
        preserved = next(item for item in migrated["articles"] if item["id"] == "real-company")
        self.assertEqual(cleaned["company"], migration.GENERIC_COMPANY)
        self.assertNotIn("companySlug", cleaned)
        self.assertEqual(cleaned["source"]["level"], "媒体报道")
        self.assertEqual(preserved["company"], "Anthropic")
        self.assertEqual(preserved["companySlug"], "anthropic")
        self.assertEqual(migrated["sourceStatus"], [])


if __name__ == "__main__":
    unittest.main()
