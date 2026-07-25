from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking
from tools import tracking_taxonomy as taxonomy


class TrackingTaxonomyTests(unittest.TestCase):
    def test_name_aliases_support_arbitrary_bilingual_tracks(self) -> None:
        self.assertEqual(
            taxonomy.name_aliases("AI / AGI"),
            ["AI / AGI", "AI", "AGI"],
        )
        self.assertEqual(
            taxonomy.name_aliases("脑机接口（BCI）"),
            ["脑机接口(BCI)", "脑机接口", "BCI"],
        )

    def test_shared_terms_are_not_unscoped_discovery_terms(self) -> None:
        tracks = [
            {
                "slug": "energy",
                "name": "新能源",
                "keywords": ["聚变能源", "长时储能"],
                "people": [],
                "sampleCompanies": ["Helion Energy", "宁德时代"],
            },
            {
                "slug": "fusion",
                "name": "可控核聚变",
                "keywords": ["聚变能源", "托卡马克"],
                "people": [],
                "sampleCompanies": [
                    "Helion Energy",
                    "Commonwealth Fusion Systems",
                ],
            },
        ]

        sources = taxonomy.generated_track_sources(tracks, tracking)
        by_id = {source["id"]: source for source in sources}

        self.assertEqual(len(sources), 6)
        self.assertEqual(
            set(taxonomy.expected_source_ids("fusion")),
            {
                "user-track-fusion-bing",
                "user-track-fusion-google-cn",
                "user-track-fusion-google-us",
            },
        )
        for suffix in taxonomy.TRACK_SOURCE_SUFFIXES:
            energy_terms = by_id[f"user-track-energy-{suffix}"]["keywords"]
            fusion_terms = by_id[f"user-track-fusion-{suffix}"]["keywords"]
            self.assertIn("长时储能", energy_terms)
            self.assertIn("托卡马克", fusion_terms)
            self.assertIn("宁德时代", energy_terms)
            self.assertIn("Commonwealth Fusion Systems", fusion_terms)
            self.assertNotIn("聚变能源", energy_terms)
            self.assertNotIn("聚变能源", fusion_terms)
            self.assertNotIn("Helion Energy", energy_terms)
            self.assertNotIn("Helion Energy", fusion_terms)
            self.assertIn("新能源", energy_terms)
            self.assertIn("可控核聚变", fusion_terms)

    def test_install_replaces_legacy_track_term_generation(self) -> None:
        original_track_terms = tracking._track_terms
        original_generated = tracking._generated_track_sources
        try:
            taxonomy.install(tracking)
            terms = tracking._track_terms(
                {
                    "slug": "bci",
                    "name": "脑机接口（BCI）",
                    "keywords": ["神经信号解码"],
                    "people": [],
                    "sampleCompanies": [],
                }
            )
            self.assertIn("脑机接口", terms)
            self.assertIn("BCI", terms)
            self.assertIn("神经信号解码", terms)
            generated = tracking._generated_track_sources(
                [
                    {
                        "slug": "bci",
                        "name": "脑机接口（BCI）",
                        "keywords": ["神经信号解码"],
                        "people": [],
                        "sampleCompanies": [],
                    }
                ]
            )
            self.assertEqual(len(generated), 3)
        finally:
            tracking._track_terms = original_track_terms
            tracking._generated_track_sources = original_generated


if __name__ == "__main__":
    unittest.main()
