from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"


class ScheduledSyncWorkflowTest(unittest.TestCase):
    def test_complete_refresh_keeps_only_the_latest_pending_writer(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: single", text)
        self.assertNotIn("queue: max", text)
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

    def test_successful_publication_gate_explicitly_dispatches_entity_reconciliation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Continue through entity reconciliation before publication", text)
        self.assertIn("steps.data-update.outcome == 'success'", text)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", text)
        self.assertIn("actions: write", text)

    def test_full_crawl_persists_audit_without_semantic_article_changes(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("No semantic public-data changes; publishing the completed full-crawl audit.", text)
        self.assertNotIn("No semantic public data changes; skipping Git commit and Pages build.", text)

    def test_full_refresh_validates_shared_source_health_summary(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("tools/source_health_summary.py", text)
        self.assertIn("tests.test_source_health_summary", text)
        self.assertIn("Require canonical source health summary", text)
        self.assertIn("python tools/source_health_summary.py --check", text)

    def test_rebase_recanonicalizes_source_health_without_double_counting_streaks(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        normalize = rebase_block.index("python tools/source_health_summary.py")
        governance = rebase_block.index("python tools/tracking_source_governance.py --check")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(normalize, governance)
        self.assertLess(governance, validate)
        self.assertNotIn("python tools/update_source_health.py", rebase_block)

    def test_rebase_rebuilds_quality_gate_before_full_refresh_validation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        rebase_block = text.split("git pull --rebase -X theirs origin main", 1)[1]
        retention = rebase_block.index("python tools/snapshot_retention.py")
        rebuild = rebase_block.index("python tools/refresh_article_quality_gate.py")
        finalize = rebase_block.index("python tools/finalize_full_refresh.py")
        validate = rebase_block.index("python tools/validate_full_refresh.py")
        self.assertLess(retention, rebuild)
        self.assertLess(rebuild, finalize)
        self.assertLess(finalize, validate)
        self.assertIn("tools/refresh_article_quality_gate.py", text)
        self.assertIn("tests.test_refresh_article_quality_gate", text)


if __name__ == "__main__":
    unittest.main()
