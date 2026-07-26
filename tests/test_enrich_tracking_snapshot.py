from __future__ import annotations

import unittest

from tools import enrich_tracking_snapshot as enrichment


class TrackingSnapshotEnrichmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = {
            "schemaVersion": 1,
            "tracks": [
                {
                    "slug": "energy",
                    "name": "新能源",
                    "enabled": True,
                    "keywords": ["长时储能"],
                    "people": [],
                    "sampleCompanies": ["宁德时代"],
                },
                {
                    "slug": "fusion",
                    "name": "可控核聚变",
                    "enabled": True,
                    "keywords": ["托卡马克", "高温超导磁体"],
                    "people": ["杨钊"],
                    "sampleCompanies": ["Helion Energy"],
                },
            ],
        }

    def test_existing_articles_are_backfilled_into_new_tracks(self) -> None:
        payload = {
            "schemaVersion": 3,
            "generatedAt": "2026-07-25T06:00:00+00:00",
            "articleCount": 2,
            "articles": [
                {
                    "id": "fusion-technology",
                    "title": "新型托卡马克完成高温超导磁体工程验证",
                    "summary": "项目团队公布最新等离子体实验结果。",
                    "sector": "新能源",
                    "company": "科技产业",
                    "authors": [],
                    "institutions": [],
                    "source": {"name": "公开媒体", "url": "https://example.com/1"},
                },
                {
                    "id": "fusion-company",
                    "title": "Helion Energy公布新一代聚变装置进度",
                    "summary": "公司更新工程建设计划。",
                    "sector": "AI / AGI",
                    "company": "Helion Energy",
                    "authors": [],
                    "institutions": [],
                    "source": {"name": "公司公告", "url": "https://example.com/2"},
                },
            ],
            "sourceStatus": [
                {
                    "id": "user-track-fusion-bing",
                    "status": "ok",
                    "scanned": 8,
                    "accepted": 1,
                },
                {
                    "id": "user-track-fusion-google-cn",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-fusion-google-us",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-fusion-toutiao",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-energy-bing",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-energy-google-cn",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-energy-google-us",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
                {
                    "id": "user-track-energy-toutiao",
                    "status": "empty",
                    "scanned": 0,
                    "accepted": 0,
                },
            ],
        }

        enriched = enrichment.enrich(payload, self.config)
        by_id = {article["id"]: article for article in enriched["articles"]}

        self.assertIn("energy", by_id["fusion-technology"]["trackSlugs"])
        self.assertIn("fusion", by_id["fusion-technology"]["trackSlugs"])
        self.assertIn("fusion", by_id["fusion-company"]["trackSlugs"])
        fusion = enriched["trackCoverage"]["fusion"]
        self.assertEqual(fusion["completedSources"], 4)
        self.assertEqual(fusion["matchedArticles"], 2)
        self.assertEqual(fusion["backfilledArticles"], 2)
        self.assertEqual(fusion["independentSources"], 2)
        self.assertEqual(fusion["status"], "ready")
        self.assertEqual(
            enriched["trackingConfigHash"],
            enrichment.tracking_config_hash(
                enrichment.enabled_tracks(self.config)
            ),
        )

    def test_missing_source_status_is_reported_as_pending(self) -> None:
        payload = {
            "schemaVersion": 3,
            "generatedAt": "2026-07-25T06:00:00+00:00",
            "articles": [],
            "sourceStatus": [],
        }
        enriched = enrichment.enrich(payload, self.config)
        self.assertEqual(
            enriched["trackCoverage"]["fusion"]["status"], "pending"
        )
        self.assertEqual(
            enriched["trackCoverage"]["fusion"]["completedSources"], 0
        )


if __name__ == "__main__":
    unittest.main()
