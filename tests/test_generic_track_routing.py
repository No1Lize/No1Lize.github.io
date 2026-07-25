from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking
from tools import tracking_taxonomy as taxonomy


class GenericTrackRoutingTests(unittest.TestCase):
    def test_arbitrary_named_tracks_generate_three_search_sources_each(self) -> None:
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
        original_track_terms = tracking._track_terms
        original_generated = tracking._generated_track_sources
        try:
            taxonomy.install(tracking)
            sources = tracking._generated_track_sources(tracks)

            self.assertEqual(len(tracks), 3)
            self.assertEqual(len(sources), 9)
            self.assertEqual(
                {source["sector"] for source in sources},
                {"可控核聚变", "脑机接口", "低空经济"},
            )
            for track in tracks:
                expected_ids = set(taxonomy.expected_source_ids(track["slug"]))
                actual = [
                    source for source in sources if source["sector"] == track["name"]
                ]
                self.assertEqual({source["id"] for source in actual}, expected_ids)
                self.assertTrue(
                    any("bing.com/search" in source["url"] for source in actual)
                )
                self.assertEqual(
                    sum(
                        "news.google.com/rss/search" in source["url"]
                        for source in actual
                    ),
                    2,
                )
                for source in actual:
                    self.assertIn(source["sector"], source["keywords"])
        finally:
            tracking._track_terms = original_track_terms
            tracking._generated_track_sources = original_generated

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
