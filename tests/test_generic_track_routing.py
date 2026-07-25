from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking


class GenericTrackRoutingTests(unittest.TestCase):
    def test_arbitrary_named_tracks_generate_search_sources(self) -> None:
        payload = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "track-a",
                    "name": "可控核聚变",
                    "enabled": True,
                    "custom": True,
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": [],
                },
                {
                    "slug": "track-b",
                    "name": "脑机接口",
                    "enabled": True,
                    "custom": True,
                    "keywords": ["神经信号解码"],
                    "people": [],
                    "sampleCompanies": ["Neuralink"],
                },
                {
                    "slug": "track-c",
                    "name": "低空经济",
                    "enabled": True,
                    "custom": True,
                    "keywords": ["eVTOL"],
                    "people": [],
                    "sampleCompanies": [],
                },
            ],
            "sources": [],
        }

        tracks = tracking._enabled_tracks(payload)
        sources = tracking._generated_track_sources(tracks)

        self.assertEqual(len(tracks), 3)
        self.assertEqual(len(sources), 3)
        self.assertEqual(
            {source["sector"] for source in sources},
            {"可控核聚变", "脑机接口", "低空经济"},
        )
        for source in sources:
            self.assertTrue(source["id"].startswith("user-track-"))
            self.assertIn(source["sector"], source["name"])
            self.assertTrue(source["url"].startswith("https://www.bing.com/search?"))
            self.assertIn(source["sector"], source["keywords"])

    def test_disabled_and_malformed_tracks_are_ignored(self) -> None:
        payload = {
            "tracks": [
                {"name": "停用赛道", "enabled": False},
                {"name": "", "enabled": True},
                "invalid",
            ]
        }
        self.assertEqual(tracking._enabled_tracks(payload), [])


if __name__ == "__main__":
    unittest.main()
