from __future__ import annotations

import unittest

from tools import enrich_fusion_tracking as fusion


class FusionTrackingEnrichmentTests(unittest.TestCase):
    def test_promotes_empty_custom_track_and_separates_energy(self) -> None:
        payload = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "energy",
                    "name": "新能源",
                    "enabled": True,
                    "custom": False,
                    "keywords": ["长时储能", "聚变能源", "固态电池"],
                    "people": [],
                    "sampleCompanies": ["宁德时代", "Helion Energy"],
                },
                {
                    "slug": "track-3p0dg3",
                    "name": "可控核聚变",
                    "enabled": True,
                    "custom": True,
                    "keywords": [],
                    "people": [],
                    "sampleCompanies": [],
                },
            ],
        }

        enriched, report = fusion.enrich(payload)
        fusion_track = next(
            track for track in enriched["tracks"] if track["name"] == "可控核聚变"
        )
        energy_track = next(
            track for track in enriched["tracks"] if track["name"] == "新能源"
        )

        self.assertEqual(fusion_track["slug"], "fusion")
        self.assertFalse(fusion_track["custom"])
        self.assertIn("托卡马克", fusion_track["keywords"])
        self.assertIn("杨钊", fusion_track["people"])
        self.assertIn("Commonwealth Fusion Systems", fusion_track["sampleCompanies"])
        self.assertNotIn("聚变能源", energy_track["keywords"])
        self.assertNotIn("Helion Energy", energy_track["sampleCompanies"])
        self.assertTrue(report["removedFusionFromEnergy"])

    def test_keeps_existing_user_entries(self) -> None:
        payload = {
            "tracks": [
                {
                    "slug": "fusion",
                    "name": "可控核聚变",
                    "enabled": False,
                    "custom": False,
                    "keywords": ["自定义聚变指标"],
                    "people": ["自定义人物"],
                    "sampleCompanies": ["自定义公司"],
                }
            ]
        }

        enriched, _ = fusion.enrich(payload)
        track = enriched["tracks"][0]

        self.assertFalse(track["enabled"])
        self.assertEqual(track["keywords"], ["自定义聚变指标"])
        self.assertEqual(track["people"], ["自定义人物"])
        self.assertEqual(track["sampleCompanies"], ["自定义公司"])

    def test_creates_track_when_missing(self) -> None:
        enriched, report = fusion.enrich({"schemaVersion": 1, "tracks": []})

        self.assertTrue(report["createdFusionTrack"])
        self.assertEqual(enriched["tracks"][0]["slug"], "fusion")
        self.assertEqual(enriched["tracks"][0]["name"], "可控核聚变")


if __name__ == "__main__":
    unittest.main()
