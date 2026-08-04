from __future__ import annotations

import unittest

from tools.source_performance_review import build_review, render_markdown, validate_report


class SourcePerformanceReviewTest(unittest.TestCase):
    def test_review_prioritizes_retirement_and_downgrade_candidates(self) -> None:
        state = {
            "generatedAt": "2026-08-31T10:00:00+00:00",
            "sources": {
                "keep": {
                    "name": "Keep",
                    "evidenceGrade": "B",
                    "collectionState": "active",
                    "priority": "normal",
                    "performance": {
                        "reviewState": "retain",
                        "runs": 10,
                        "availabilityRate": 1.0,
                        "productiveRate": 0.8,
                    },
                },
                "retire": {
                    "name": "Retire",
                    "evidenceGrade": "D",
                    "collectionState": "quarantined",
                    "priority": "low",
                    "performance": {
                        "reviewState": "retire-candidate",
                        "reviewReasons": ["low-availability", "quarantined"],
                        "reviewReasonLabels": ["抓取成功率低于阈值", "来源处于发布隔离或恢复观察"],
                        "runs": 30,
                        "availabilityRate": 0.1,
                        "productiveRate": 0.0,
                        "validYieldRate": 0.0,
                        "duplicateRate": None,
                    },
                },
                "downgrade": {
                    "name": "Downgrade",
                    "evidenceGrade": "C",
                    "collectionState": "active",
                    "priority": "normal",
                    "performance": {
                        "reviewState": "downgrade-candidate",
                        "reviewReasons": ["high-duplicate-rate", "low-productivity"],
                        "reviewReasonLabels": ["已接收候选重复率过高", "有效产出频率低于阈值"],
                        "runs": 20,
                        "availabilityRate": 0.8,
                        "productiveRate": 0.1,
                        "duplicateRate": 0.9,
                    },
                },
            },
        }
        report = build_review(state, {})
        self.assertEqual(report["sourceCount"], 3)
        self.assertEqual(report["reviewRequiredSourceCount"], 2)
        self.assertEqual(report["sources"][0]["sourceId"], "retire")
        self.assertEqual(report["sources"][1]["sourceId"], "downgrade")
        self.assertEqual(validate_report(report), [])

        markdown = render_markdown(report)
        self.assertIn("建议停用候选", markdown)
        self.assertIn("建议降级候选", markdown)
        self.assertNotIn("| Keep |", markdown)

    def test_manual_review_metrics_are_exposed(self) -> None:
        state = {
            "generatedAt": "2026-08-31T10:00:00+00:00",
            "sources": {
                "source-a": {
                    "name": "Source A",
                    "performance": {"reviewState": "monitor", "runs": 5},
                }
            },
        }
        manual = {
            "source-a": {
                "reviewedRecords": 20,
                "misattributedRecords": 2,
                "confirmedDuplicateRecords": 1,
                "misattributionRate": 0.1,
                "lastReviewedAt": "2026-08-30T00:00:00Z",
                "reviewer": "reviewer",
            }
        }
        report = build_review(state, manual)
        row = report["sources"][0]
        self.assertEqual(row["reviewedRecords"], 20)
        self.assertEqual(row["misattributionRate"], 0.1)
        self.assertEqual(report["manualReviewCoverage"]["reviewedSources"], 1)


if __name__ == "__main__":
    unittest.main()
