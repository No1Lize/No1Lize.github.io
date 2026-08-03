from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "company-profile-incremental-refresh.yml"


class CompanyProfileIncrementalWorkflowTests(unittest.TestCase):
    def test_schedule_is_staggered_three_times_daily(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('cron: "35 13,17,21 * * *"', text)
        self.assertIn('timezone: "Asia/Taipei"', text)

    def test_article_updates_do_not_directly_trigger_profile_crawls(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("public/data/articles.json", text)
        self.assertNotIn("gh workflow run", text)

    def test_writer_queue_and_hard_company_cap_are_preserved(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)
        self.assertIn("max(1, min(10, value))", text)
        self.assertIn("--kind company", text)
        self.assertIn('--slug "$slug"', text)

    def test_profiles_are_only_committed_after_quality_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        validation = text.index("python tools/crawl_venture_profiles.py --validate-only")
        commit = text.index('git commit -m "data: process queued company profile refreshes"')
        self.assertLess(validation, commit)


if __name__ == "__main__":
    unittest.main()
