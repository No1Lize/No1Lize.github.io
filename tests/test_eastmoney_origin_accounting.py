from __future__ import annotations

import unittest

from tools.eastmoney_transport import (
    EASTMONEY_ORIGIN_FIELD,
    EASTMONEY_ORIGIN_NEW,
    EASTMONEY_ORIGIN_RETAINED,
    merge_eastmoney_history,
)
from tools.refine_eastmoney_snapshot import refine_snapshot


SOURCE_ID = "official-user-东方财富"


def article(
    article_id: str,
    title: str,
    *,
    sequence: int,
    summary: str = "人工智能与半导体产业取得新进展。",
    origin: str = "",
) -> dict:
    item = {
        "id": article_id,
        "sourceId": SOURCE_ID,
        "title": title,
        "summary": summary,
        "type": "公司动态",
        "region": "全球",
        "sector": "半导体",
        "company": "科技产业",
        "publishedAt": "2026-07-25",
        "importance": 80,
        "source": {
            "name": "东方财富",
            "url": f"https://finance.eastmoney.com/a/20260725{3821000000 + sequence}.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }
    if origin:
        item[EASTMONEY_ORIGIN_FIELD] = origin
    return item


def source_status(**updates) -> dict:
    value = {
        "id": SOURCE_ID,
        "name": "东方财富",
        "status": "ok",
        "accepted": 0,
        "failed": 0,
        "platform": "东方财富",
    }
    value.update(updates)
    return value


class EastmoneyOriginAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracking = {
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
            ]
        }

    def test_merge_marks_new_and_retained_articles(self) -> None:
        existing = [
            article(
                "old",
                "三星电子与博通合作开发先进内存芯片",
                sequence=1,
            )
        ]
        incoming = [
            article(
                "new",
                "SK海力士推进新一代AI芯片合作",
                sequence=2,
            )
        ]
        status = source_status(accepted=1)

        merged = merge_eastmoney_history(existing, incoming, [status])
        origins = {item["id"]: item[EASTMONEY_ORIGIN_FIELD] for item in merged}

        self.assertEqual(origins["new"], EASTMONEY_ORIGIN_NEW)
        self.assertEqual(origins["old"], EASTMONEY_ORIGIN_RETAINED)
        self.assertEqual(status["newAccepted"], 1)
        self.assertEqual(status["retainedPreviousCount"], 1)

    def test_refinement_recounts_after_retained_roundup_is_removed(self) -> None:
        snapshot = {
            "articleCount": 3,
            "articles": [
                article(
                    "new-valid",
                    "SK海力士推进新一代AI芯片合作",
                    sequence=3,
                    origin=EASTMONEY_ORIGIN_NEW,
                ),
                article(
                    "retained-valid",
                    "三星电子与博通合作开发先进内存芯片",
                    sequence=4,
                    origin=EASTMONEY_ORIGIN_RETAINED,
                ),
                article(
                    "retained-roundup",
                    "凌晨全线大跌！美股半导体板块集体重挫",
                    sequence=5,
                    summary="昨夜今晨多个市场板块下跌。",
                    origin=EASTMONEY_ORIGIN_RETAINED,
                ),
            ],
            "sourceStatus": [
                source_status(
                    accepted=3,
                    newAccepted=1,
                    retainedPrevious=True,
                    retainedPreviousCount=2,
                )
            ],
        }

        refined, report = refine_snapshot(snapshot, self.tracking)
        status = refined["sourceStatus"][0]

        self.assertEqual(refined["articleCount"], 2)
        self.assertEqual(status["accepted"], 2)
        self.assertEqual(status["newAccepted"], 1)
        self.assertEqual(status["retainedPreviousCount"], 1)
        self.assertTrue(status["retainedPrevious"])
        self.assertEqual(report["eastmoneyNewKept"], 1)
        self.assertEqual(report["eastmoneyRetainedKept"], 1)
        self.assertEqual(
            report["removedRoundups"],
            ["凌晨全线大跌！美股半导体板块集体重挫"],
        )
        self.assertTrue(
            all(
                EASTMONEY_ORIGIN_FIELD not in item
                for item in refined["articles"]
            )
        )

    def test_repeated_refinement_preserves_closed_accounting(self) -> None:
        snapshot = {
            "articleCount": 2,
            "articles": [
                article(
                    "new-valid",
                    "SK海力士推进新一代AI芯片合作",
                    sequence=8,
                    origin=EASTMONEY_ORIGIN_NEW,
                ),
                article(
                    "retained-valid",
                    "三星电子与博通合作开发先进内存芯片",
                    sequence=9,
                    origin=EASTMONEY_ORIGIN_RETAINED,
                ),
            ],
            "sourceStatus": [
                source_status(
                    accepted=2,
                    newAccepted=1,
                    retainedPrevious=True,
                    retainedPreviousCount=1,
                )
            ],
        }

        first, _ = refine_snapshot(snapshot, self.tracking)
        second, _ = refine_snapshot(first, self.tracking)

        self.assertEqual(first["articles"], second["articles"])
        self.assertEqual(first["sourceStatus"], second["sourceStatus"])
        status = second["sourceStatus"][0]
        self.assertEqual(status["accepted"], 2)
        self.assertEqual(status["newAccepted"], 1)
        self.assertEqual(status["retainedPreviousCount"], 1)
        self.assertTrue(status["retainedPrevious"])
        self.assertTrue(
            all(
                EASTMONEY_ORIGIN_FIELD not in item
                for item in second["articles"]
            )
        )

    def test_clean_empty_discovery_counts_all_survivors_as_retained(self) -> None:
        snapshot = {
            "articleCount": 1,
            "articles": [
                article(
                    "cached-valid",
                    "三星电子与博通合作开发先进内存芯片",
                    sequence=6,
                )
            ],
            "sourceStatus": [
                source_status(
                    accepted=0,
                    status="partial",
                    retainedPrevious=True,
                    error="previous detail snapshot retained",
                )
            ],
        }

        refined, _ = refine_snapshot(snapshot, self.tracking)
        status = refined["sourceStatus"][0]

        self.assertEqual(status["accepted"], 1)
        self.assertEqual(status["newAccepted"], 0)
        self.assertEqual(status["retainedPreviousCount"], 1)
        self.assertTrue(status["retainedPrevious"])
        self.assertEqual(status["status"], "partial")

    def test_all_filtered_articles_clear_retention_metadata(self) -> None:
        snapshot = {
            "articleCount": 1,
            "articles": [
                article(
                    "roundup-only",
                    "东方财富财经早报",
                    sequence=7,
                    summary="今日市场新闻汇总。",
                    origin=EASTMONEY_ORIGIN_RETAINED,
                )
            ],
            "sourceStatus": [
                source_status(
                    accepted=1,
                    status="partial",
                    newAccepted=0,
                    retainedPrevious=True,
                    retainedPreviousCount=1,
                )
            ],
        }

        refined, _ = refine_snapshot(snapshot, self.tracking)
        status = refined["sourceStatus"][0]

        self.assertEqual(refined["articleCount"], 0)
        self.assertEqual(status["accepted"], 0)
        self.assertEqual(status["newAccepted"], 0)
        self.assertNotIn("retainedPrevious", status)
        self.assertNotIn("retainedPreviousCount", status)
        self.assertEqual(status["status"], "empty")


if __name__ == "__main__":
    unittest.main()
