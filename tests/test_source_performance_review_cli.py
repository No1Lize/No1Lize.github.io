from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "source_performance_review.py"


class SourcePerformanceReviewCliTest(unittest.TestCase):
    def test_cli_writes_and_validates_review_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "source_health.json"
            reviews = root / "reviews.json"
            output_json = root / "review.json"
            output_markdown = root / "review.md"
            state.write_text(
                json.dumps(
                    {
                        "schemaVersion": 3,
                        "generatedAt": "2026-08-31T10:00:00+00:00",
                        "sources": {
                            "source-a": {
                                "name": "Source A",
                                "evidenceGrade": "C",
                                "collectionState": "quarantined",
                                "priority": "low",
                                "performance": {
                                    "reviewState": "retire-candidate",
                                    "reviewReasons": ["low-availability"],
                                    "reviewReasonLabels": ["抓取成功率低于阈值"],
                                    "runs": 30,
                                    "availabilityRate": 0.1,
                                    "productiveRate": 0.0,
                                },
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            reviews.write_text(
                json.dumps({"schemaVersion": 1, "reviews": []}),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--state",
                    str(state),
                    "--reviews",
                    str(reviews),
                    "--json",
                    str(output_json),
                    "--markdown",
                    str(output_markdown),
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--json",
                    str(output_json),
                    "--check",
                ],
                check=True,
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

            payload = json.loads(output_json.read_text(encoding="utf-8"))
            self.assertEqual(payload["period"], "2026-08")
            self.assertEqual(payload["reviewRequiredSourceCount"], 1)
            self.assertIn("Source A", output_markdown.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
