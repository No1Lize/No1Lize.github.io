from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking
from tools import tracking_taxonomy as taxonomy


class TrackingTaxonomyTests(unittest.TestCase):
    def test_name_aliases_support_arbitrary_bilingual_tracks(self) -> None:
        self.assertEqual(
            taxonomy.name_aliases("AI / AGI"),
            ["AI / AGI", "AI/AGI", "AI", "AGI"],
        )
        self.assertEqual(
            taxonomy.name_aliases("脑机接口（BCI）"),
            ["脑机接口(BCI)", "脑机接口", "BCI"],
        )

    def test_shared_actors_are_not_unscoped_discovery_terms(self) -> None:
        tracks = [
            {
                "slug": "energy",
                "name": "新能源",
                "keywords": ["长时储能"],
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

        energy_terms = by_id["user-track-energy"]["keywords"]
        fusion_terms = by_id["user-track-fusion"]["keywords"]
        self.assertIn("宁德时代", energy_terms)
        self.assertIn("Commonwealth Fusion Systems", fusion_terms)
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
        finally:
            tracking._track_terms = original_track_terms
            tracking._generated_track_sources = original_generated


if __name__ == "__main__":
    unittest.main()
