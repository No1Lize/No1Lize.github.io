from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.source_quality_reviews import load_review_manifest, review_index


class SourceQualityReviewTest(unittest.TestCase):
    def _write(self, payload: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "reviews.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_valid_reviews_aggregate_manual_error_rates(self) -> None:
        payload = {
            "schemaVersion": 1,
            "reviews": [
                {
                    "sourceId": "source-a",
                    "period": "2026-07",
                    "reviewedRecords": 20,
                    "misattributedRecords": 1,
                    "confirmedDuplicateRecords": 2,
                    "reviewer": "reviewer-a",
                    "reviewedAt": "2026-07-31T10:00:00Z",
                    "notes": "sample one",
                },
                {
                    "sourceId": "source-a",
                    "period": "2026-08",
                    "reviewedRecords": 30,
                    "misattributedRecords": 2,
                    "confirmedDuplicateRecords": 1,
                    "reviewer": "reviewer-b",
                    "reviewedAt": "2026-08-31T10:00:00Z",
                },
            ],
        }
        manifest = load_review_manifest(self._write(payload))
        item = review_index(manifest)["source-a"]
        self.assertEqual(item["reviewedRecords"], 50)
        self.assertEqual(item["misattributedRecords"], 3)
        self.assertEqual(item["confirmedDuplicateRecords"], 3)
        self.assertEqual(item["misattributionRate"], 0.06)
        self.assertEqual(item["reviewer"], "reviewer-b")

    def test_duplicate_source_period_is_rejected(self) -> None:
        row = {
            "sourceId": "source-a",
            "period": "2026-08",
            "reviewedRecords": 20,
            "misattributedRecords": 1,
            "confirmedDuplicateRecords": 0,
            "reviewer": "reviewer",
            "reviewedAt": "2026-08-31T10:00:00Z",
        }
        path = self._write({"schemaVersion": 1, "reviews": [row, row]})
        with self.assertRaisesRegex(ValueError, "duplicate review"):
            load_review_manifest(path)

    def test_invalid_counts_are_rejected(self) -> None:
        path = self._write(
            {
                "schemaVersion": 1,
                "reviews": [
                    {
                        "sourceId": "source-a",
                        "period": "2026-08",
                        "reviewedRecords": 10,
                        "misattributedRecords": 11,
                        "confirmedDuplicateRecords": 0,
                        "reviewer": "reviewer",
                        "reviewedAt": "2026-08-31T10:00:00Z",
                    }
                ],
            }
        )
        with self.assertRaisesRegex(ValueError, "misattributedRecords"):
            load_review_manifest(path)


if __name__ == "__main__":
    unittest.main()
