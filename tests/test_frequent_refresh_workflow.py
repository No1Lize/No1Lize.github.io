from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "frequent-intelligence-refresh.yml"


class FrequentRefreshWorkflowTests(unittest.TestCase):
    def test_lightweight_schedule_reserves_the_full_refresh_window(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "17 0,2,4,8,10,12,14,16,18,20,22 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)
        self.assertNotIn('cron: "47 */2 * * *"', text)

    def test_lightweight_refresh_uses_the_repository_writer_queue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_due_check_reads_main_after_the_writer_lock_is_acquired(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        checkout = text.index("- uses: actions/checkout@v4")
        due_check = text.index("- name: Skip refresh when the current snapshot is still recent")
        self.assertLess(checkout, due_check)
        checkout_block = text[checkout:due_check]
        self.assertIn("ref: main", checkout_block)
        self.assertIn("fetch-depth: 0", checkout_block)

    def test_lightweight_refresh_only_crawls_news_families(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/crawl_with_wechat_registry.py --source news", text)
        self.assertIn("python tools/finalize_frequent_refresh.py", text)
        self.assertNotIn("python -m tools.us_ir_baseline_disclosures", text)
        self.assertNotIn("python tools/refresh_market_profiles_enriched.py", text)
        self.assertNotIn("python tools/refresh_people_profiles_with_video.py", text)

    def test_semantic_change_uses_the_single_push_deploy_path(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/semantic_data_diff.py", text)
        self.assertIn('git commit -m "data: refresh public intelligence (two-hour check)"', text)
        self.assertNotIn("gh workflow run pages.yml --ref main", text)


if __name__ == "__main__":
    unittest.main()
