from __future__ import annotations

import unittest

from tools.eastmoney_transport import merge_eastmoney_history
from tools.migrate_article_entities import migrate
from tools.refine_eastmoney_snapshot import refine_snapshot
from tools.validate_eastmoney_snapshot import validate_snapshot


SOURCE_ID = "official-user-东方财富"


def tracking() -> dict:
    return {
        "sources": [
            {
                "id": "source-track-eastmoney",
                "name": "东方财富",
                "url": "https://www.eastmoney.com/default.html",
                "sourceType": "listing-search",
                "sourceCategory": "media",
                "company": "",
                "enabled": True,
            }
        ],
        "listedCompanies": [
            {
                "id": "catalog-cambricon",
                "name": "寒武纪",
                "ticker": "688256",
                "market": "A股",
                "sector": "半导体",
                "enabled": True,
                "catalogSlug": "cambricon",
            }
        ],
    }


def article(
    article_id: str,
    title: str,
    *,
    sequence: int,
    summary: str = "人工智能与半导体产业取得新进展。",
    published_at: str = "2026-07-25",
) -> dict:
    return {
        "id": article_id,
        "sourceId": SOURCE_ID,
        "title": title,
        "summary": summary,
        "type": "公司动态",
        "region": "全球",
        "sector": "半导体",
        "company": "科技产业",
        "publishedAt": published_at,
        "importance": 80,
        "source": {
            "name": "东方财富",
            "url": f"https://finance.eastmoney.com/a/20260725{3821000000 + sequence}.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }


def status(accepted: int) -> dict:
    return {
        "id": SOURCE_ID,
        "name": "东方财富 官方动态",
        "company": "东方财富",
        "status": "ok",
        "accepted": accepted,
        "failed": 0,
        "platform": "东方财富",
    }


class EastmoneySnapshotPipelineTests(unittest.TestCase):
    def test_complete_pipeline_preserves_status_and_closes_accounting(self) -> None:
        existing = [
            article(
                "retained-valid",
                "三星电子与博通合作开发先进内存芯片",
                sequence=1,
                published_at="2026-07-24",
            ),
            article(
                "retained-roundup",
                "凌晨全线大跌！美股半导体板块集体重挫",
                sequence=2,
                summary="昨夜今晨多个市场板块下跌。",
                published_at="2026-07-24",
            ),
        ]
        incoming = [
            article(
                "new-valid",
                "SK海力士推进新一代AI芯片合作",
                sequence=3,
            )
        ]
        public_status = status(accepted=1)

        merged = merge_eastmoney_history(
            existing,
            incoming,
            [public_status],
        )
        payload = {
            "schemaVersion": 3,
            "articleCount": len(merged),
            "articles": merged,
            "sourceStatus": [public_status],
        }

        migrated, migration_report = migrate(payload, tracking())
        refined, refinement_report = refine_snapshot(migrated, tracking())
        validation_report = validate_snapshot(
            refined,
            tracking(),
            require_attempt=True,
        )

        self.assertEqual(migration_report["removedLegacyStatuses"], 0)
        self.assertEqual(
            {item["id"] for item in refined["articles"]},
            {"new-valid", "retained-valid"},
        )
        self.assertEqual(
            refinement_report["removedRoundups"],
            ["凌晨全线大跌！美股半导体板块集体重挫"],
        )
        self.assertEqual(len(refined["sourceStatus"]), 1)
        final_status = refined["sourceStatus"][0]
        self.assertEqual(final_status["accepted"], 2)
        self.assertEqual(final_status["newAccepted"], 1)
        self.assertEqual(final_status["retainedPreviousCount"], 1)
        self.assertTrue(final_status["retainedPrevious"])
        self.assertEqual(validation_report["detailArticles"], 2)
        self.assertEqual(validation_report["acceptedByCrawler"], 2)
        self.assertEqual(validation_report["missingDetailStatusIds"], [])
        self.assertEqual(validation_report["leakedInternalFields"], [])
        self.assertEqual(validation_report["accountingErrors"], [])
        self.assertTrue(
            all(
                "_eastmoneyBatchOrigin" not in item
                for item in refined["articles"]
            )
        )

    def test_second_refinement_remains_valid(self) -> None:
        items = [
            article(
                "retained-valid",
                "三星电子与博通合作开发先进内存芯片",
                sequence=4,
                published_at="2026-07-24",
            )
        ]
        incoming = [
            article(
                "new-valid",
                "SK海力士推进新一代AI芯片合作",
                sequence=5,
            )
        ]
        public_status = status(accepted=1)
        merged = merge_eastmoney_history(items, incoming, [public_status])
        payload = {
            "articleCount": len(merged),
            "articles": merged,
            "sourceStatus": [public_status],
        }

        migrated, _ = migrate(payload, tracking())
        first, _ = refine_snapshot(migrated, tracking())
        second, _ = refine_snapshot(first, tracking())
        report = validate_snapshot(second, tracking(), require_attempt=True)

        self.assertEqual(first["articles"], second["articles"])
        self.assertEqual(first["sourceStatus"], second["sourceStatus"])
        self.assertEqual(report["acceptedByCrawler"], 2)
        self.assertEqual(report["detailArticles"], 2)


if __name__ == "__main__":
    unittest.main()
