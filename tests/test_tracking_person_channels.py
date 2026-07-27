import unittest

from tools.enrich_tracking_people_from_sample_companies import empty_ledger
from tools.enrich_tracking_person_channels import (
    classify_public_channel,
    enrich_public_channels,
)


class TrackingPersonChannelTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "robotics",
                    "name": "机器人",
                    "enabled": True,
                    "custom": False,
                    "keywords": ["具身智能"],
                    "people": [],
                    "sampleCompanies": ["Example Robotics"],
                }
            ],
            "listedCompanies": [],
            "sources": [],
        }
        self.venture = {
            "companies": {
                "example-robotics": {
                    "slug": "example-robotics",
                    "name": "Example Robotics",
                    "team": [
                        {
                            "name": "Alice Chen",
                            "role": "联合创始人兼 CEO",
                            "sourceUrl": "https://example.com/team",
                        },
                        {
                            "name": "Bob Li",
                            "role": "CTO",
                            "sourceUrl": "https://example.com/team",
                        },
                    ],
                }
            }
        }
        self.people = {
            "people": [
                {
                    "name": "Alice Chen",
                    "aliases": [],
                    "materials": [
                        {
                            "title": "Alice 的微信公开文章",
                            "type": "article",
                            "url": "https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=xyz",
                            "source": "微信公众号",
                        },
                        {
                            "title": "Alice Chen",
                            "type": "social_profile",
                            "url": "https://www.zhihu.com/people/alice-chen",
                            "source": "知乎",
                        },
                        {
                            "title": "Alice Chen on Medium",
                            "type": "column",
                            "url": "https://medium.com/@alicechen",
                            "source": "Medium",
                        },
                        {
                            "title": "Alice Chen author page",
                            "type": "author_profile",
                            "url": "https://techcrunch.com/author/alice-chen/",
                            "source": "TechCrunch",
                        },
                        {
                            "title": "普通采访文章",
                            "type": "interview",
                            "url": "https://example.com/news/alice-interview",
                            "source": "Example News",
                        },
                        {
                            "title": "Alice Chen — Wikipedia",
                            "type": "biography",
                            "url": "https://en.wikipedia.org/wiki/Alice_Chen",
                            "source": "Wikipedia",
                        },
                    ],
                }
            ]
        }

    def test_classifies_supported_public_channels(self):
        self.assertEqual(
            classify_public_channel("https://mp.weixin.qq.com/s?__biz=abc").platform,
            "微信公开材料",
        )
        self.assertEqual(
            classify_public_channel("https://www.zhihu.com/people/alice-chen").platform,
            "知乎",
        )
        self.assertEqual(
            classify_public_channel("https://techcrunch.com/author/alice-chen/").platform,
            "媒体专栏",
        )
        self.assertIsNone(
            classify_public_channel("https://example.com/news/alice-interview")
        )

    def test_adds_verified_channels_for_core_team(self):
        ledger = empty_ledger()
        result = enrich_public_channels(
            self.config,
            self.venture,
            self.people,
            ledger,
            10,
        )

        self.assertTrue(result["changed"])
        urls = {source["url"] for source in self.config["sources"]}
        self.assertIn(
            "https://mp.weixin.qq.com/s?__biz=abc&mid=1&idx=1&sn=xyz",
            urls,
        )
        self.assertIn("https://www.zhihu.com/people/alice-chen", urls)
        self.assertIn("https://medium.com/@alicechen", urls)
        self.assertIn("https://techcrunch.com/author/alice-chen/", urls)
        self.assertNotIn("https://example.com/news/alice-interview", urls)
        self.assertTrue(
            all(source["sourceCategory"] == "person" for source in self.config["sources"])
        )
        self.assertTrue(
            all("Alice Chen" in source["keywords"] for source in self.config["sources"])
        )

    def test_existing_source_is_not_duplicated(self):
        self.config["sources"].append(
            {
                "id": "existing-alice-zhihu",
                "name": "Alice Chen · 知乎",
                "url": "https://www.zhihu.com/people/alice-chen",
                "sourceType": "listing-search",
                "sourceCategory": "person",
                "region": "中国",
                "sector": "机器人",
                "company": "",
                "ticker": "",
                "keywords": ["Alice Chen"],
                "enabled": True,
            }
        )
        enrich_public_channels(
            self.config,
            self.venture,
            self.people,
            empty_ledger(),
            10,
        )
        self.assertEqual(
            [source["url"] for source in self.config["sources"]].count(
                "https://www.zhihu.com/people/alice-chen"
            ),
            1,
        )

    def test_removed_auto_source_is_not_readded(self):
        ledger = empty_ledger()
        ledger["removed"].append(
            {
                "track": "robotics",
                "kind": "sources",
                "value": "https://www.zhihu.com/people/alice-chen",
                "removedAt": "2026-07-27T00:00:00+00:00",
            }
        )
        enrich_public_channels(
            self.config,
            self.venture,
            self.people,
            ledger,
            10,
        )
        self.assertNotIn(
            "https://www.zhihu.com/people/alice-chen",
            {source["url"] for source in self.config["sources"]},
        )


if __name__ == "__main__":
    unittest.main()
