from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"


class ScheduledSyncWorkflowTest(unittest.TestCase):
    def test_complete_refresh_is_queued_not_cancelled(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: public-article-refresh", text)
        self.assertIn("cancel-in-progress: false", text)
        self.assertNotIn("cancel-in-progress: true", text)

    def test_full_refresh_covers_required_source_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        required_commands = (
            "python tools/crawl_with_wechat_registry.py --source all",
            "python tools/validate_professional_media_snapshot.py --require-articles",
            "python tools/crawl_listed_company_disclosures.py",
            "python tools/cninfo_structured_disclosures.py --require-events",
            "python tools/cninfo_structured_disclosures.py --check --require-events",
            "python tools/eastmoney_transport.py",
            "python tools/validate_full_refresh.py",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()
