from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"


class ScheduledSyncWorkflowTest(unittest.TestCase):
    def test_complete_refresh_uses_the_repository_writer_queue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_full_refresh_runs_once_daily_after_the_us_close(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "30 6 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertNotIn("4-22/2", text)

    def test_tracking_config_changes_start_one_full_refresh(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("      - config/user_tracking.json", text)

    def test_full_refresh_covers_required_source_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        required_commands = (
            "python tools/crawl_with_wechat_registry.py --source all",
            "python tools/validate_professional_media_snapshot.py --require-articles",
            "python tools/crawl_listed_company_disclosures.py",
            "python tools/cninfo_structured_disclosures.py --require-events",
            "python -m tools.publish_us_ir_baselines",
            "python -m tools.us_ir_baseline_disclosures",
            "python -m tools.us_ir_baseline_disclosures --check --require-events",
            "python tools/eastmoney_transport.py",
            "python tools/validate_full_refresh.py",
        )
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()
