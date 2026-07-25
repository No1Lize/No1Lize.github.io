from __future__ import annotations

import json
import unittest

from tools.validate_eastmoney_snapshot import validate_snapshot


SOURCE_ID = "official-user-东方财富"
DETAIL_URL = "https://finance.eastmoney.com/a/202607253821110827.html"


def tracking() -> dict:
    return {
        "sources": [
            {
                "id": "user-source-eastmoney",
                "name": "东方财富",
                "company": "东方财富",
                "url": "https://fund.eastmoney.com/a/cjjyw.html",
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
            "url": DETAIL_URL,
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }
    if internal:
        value["_eastmoneyBatchOrigin"] = "retained"
    return value


def status(**updates) -> dict:
    value = {
        "id": SOURCE_ID,
        "name": "东方财富",
        "status": "ok",
        "accepted": 1,
        "failed": 0,
        "platform": "东方财富",
    }
    value.update(updates)
    return value


def snapshot(*, articles: list[dict] | None = None, statuses: list[dict] | None = None) -> dict:
    values = articles if articles is not None else [article()]
    return {
        "articleCount": len(values),
        "articles": values,
        "sourceStatus": statuses if statuses is not None else [status()],
    }


class EastmoneyPipelineMetadataValidationTests(unittest.TestCase):
    def assert_validation_error(self, payload: dict, expected: str) -> dict:
        with self.assertRaises(ValueError) as context:
            validate_snapshot(payload, tracking(), require_attempt=True)
        report = json.loads(str(context.exception))
        self.assertTrue(any(expected in error for error in report["errors"]))
        return report

    def test_valid_final_accounting_passes(self) -> None:
        payload = snapshot(
            statuses=[
                status(
                    accepted=1,
                    newAccepted=0,
                    retainedPrevious=True,
                    retainedPreviousCount=1,
                )
            ]
        )

        report = validate_snapshot(payload, tracking(), require_attempt=True)

        self.assertEqual(report["detailArticles"], 1)
        self.assertEqual(report["acceptedByCrawler"], 1)
        self.assertEqual(report["leakedInternalFields"], [])
        self.assertEqual(report["accountingErrors"], [])

    def test_internal_origin_field_is_rejected(self) -> None:
        report = self.assert_validation_error(
            snapshot(articles=[article(internal=True)]),
            "流水线内部字段",
        )

        self.assertEqual(len(report["leakedInternalFields"]), 1)
        self.assertIn("_eastmoneyBatchOrigin", report["leakedInternalFields"][0])

    def test_rolling_counts_must_sum_to_accepted(self) -> None:
        report = self.assert_validation_error(
            snapshot(
                statuses=[
                    status(
                        accepted=3,
                        newAccepted=1,
                        retainedPrevious=True,
                        retainedPreviousCount=1,
                    )
                ]
            ),
            "滚动历史计数不闭合",
        )

        self.assertEqual(len(report["accountingErrors"]), 1)
        self.assertIn("accepted=3", report["accountingErrors"][0])

    def test_accepted_must_match_final_detail_count(self) -> None:
        report = self.assert_validation_error(
            snapshot(statuses=[status(accepted=2)]),
            "accepted 与最终详情文章数不一致",
        )

        self.assertEqual(report["acceptedByCrawler"], 2)
        self.assertEqual(report["detailArticles"], 1)

    def test_retained_count_requires_retained_flag(self) -> None:
        report = self.assert_validation_error(
            snapshot(
                statuses=[
                    status(
                        accepted=1,
                        newAccepted=0,
                        retainedPreviousCount=1,
                    )
                ]
            ),
            "滚动历史计数不闭合",
        )

        self.assertIn("未标记 retainedPrevious", report["accountingErrors"][0])

    def test_concrete_user_source_detail_is_not_a_generic_duplicate(self) -> None:
        payload = snapshot(
            articles=[article(source_id="user-source-eastmoney")],
            statuses=[
                {
                    "id": "user-source-eastmoney",
                    "name": "东方财富",
                    "status": "ok",
                    "accepted": 1,
                    "failed": 0,
                    "platform": "东方财富",
                }
            ],
        )

        report = validate_snapshot(payload, tracking(), require_attempt=True)

        self.assertEqual(report["genericDuplicates"], [])
        self.assertEqual(report["detailArticles"], 1)


if __name__ == "__main__":
    unittest.main()
