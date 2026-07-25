from __future__ import annotations

import unittest

from tools.migrate_article_entities import migrate


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
        ]
    }


def article(*, source_id: str = SOURCE_ID, internal: bool = False) -> dict:
    value = {
        "id": "eastmoney-detail",
        "sourceId": source_id,
        "title": "三星电子与博通合作开发先进内存芯片",
        "summary": "双方签署先进内存芯片合作协议。",
        "company": "科技产业",
        "publishedAt": "2026-07-25",
        "source": {
            "name": "东方财富",
            "url": "https://finance.eastmoney.com/a/202607253821110827.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }
    if internal:
        value["_eastmoneyBatchOrigin"] = "retained"
    return value


def status(source_id: str = SOURCE_ID) -> dict:
    return {
        "id": source_id,
        "name": "东方财富 官方动态",
        "company": "东方财富",
        "status": "ok",
        "accepted": 1,
        "failed": 0,
        "platform": "东方财富",
    }


class SpecializedMediaStatusMigrationTests(unittest.TestCase):
    def test_status_is_preserved_when_surviving_article_uses_source_id(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [status()],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(migrated["sourceStatus"], [status()])
        self.assertEqual(report["removedLegacyStatuses"], 0)
        self.assertEqual(migrated["articles"][0]["sourceId"], SOURCE_ID)

    def test_orphaned_legacy_status_is_removed(self) -> None:
        payload = {
            "articleCount": 0,
            "articles": [],
            "sourceStatus": [status()],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(migrated["sourceStatus"], [])
        self.assertEqual(report["removedLegacyStatuses"], 1)

    def test_unrelated_status_is_not_removed(self) -> None:
        unrelated = {
            "id": "official-anthropic",
            "name": "Anthropic 官方动态",
            "status": "ok",
            "accepted": 1,
        }
        payload = {
            "articleCount": 1,
            "articles": [article()],
            "sourceStatus": [status(), unrelated],
        }

        migrated, report = migrate(payload, tracking())

        self.assertEqual(
            {item["id"] for item in migrated["sourceStatus"]},
            {SOURCE_ID, "official-anthropic"},
        )
        self.assertEqual(report["removedLegacyStatuses"], 0)

    def test_internal_origin_marker_survives_migration_for_refinement(self) -> None:
        payload = {
            "articleCount": 1,
            "articles": [article(internal=True)],
            "sourceStatus": [status()],
        }

        migrated, _ = migrate(payload, tracking())

        self.assertEqual(
            migrated["articles"][0]["_eastmoneyBatchOrigin"],
            "retained",
        )


if __name__ == "__main__":
    unittest.main()
