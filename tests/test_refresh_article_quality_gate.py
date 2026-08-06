from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from tools.refresh_article_quality_gate import ARTICLES_PATH, rebuild_quality_gate


class RefreshArticleQualityGateTests(unittest.TestCase):
    def test_rebuilds_a_stale_gate_and_reaches_a_fixed_point(self) -> None:
        payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, dict)
        stale = copy.deepcopy(payload)
        stale["qualityGate"] = {"passed": False, "checks": {}}

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "articles.json"
            target.write_text(
                json.dumps(stale, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            quality, changed = rebuild_quality_gate(target)
            self.assertTrue(changed)
            self.assertTrue(quality["passed"])
            written = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(written["qualityGate"], quality)

            fixed_quality, fixed_changed = rebuild_quality_gate(target)
            self.assertFalse(fixed_changed)
            self.assertEqual(fixed_quality, quality)


if __name__ == "__main__":
    unittest.main()
