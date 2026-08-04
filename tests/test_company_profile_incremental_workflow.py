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

    def test_only_schedule_or_manual_dispatch_starts_a_profile_crawl(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\n  push:\n", text)
        self.assertNotIn("public/data/articles.json", text)
        self.assertNotIn("gh workflow run", text)

    def test_writer_queue_and_hard_company_cap_are_preserved(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)
        self.assertIn("max(1, min(10, value))", text)
        self.assertIn("--kind company", text)
        self.assertIn('--slug "$slug"', text)

    def test_all_publication_gates_share_one_fixed_point(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("python tools/stabilize_venture_publication_pipeline.py", text)
        self.assertIn(
            "python tools/stabilize_venture_publication_pipeline.py --check", text
        )
        self.assertIn("python tools/stabilize_venture_research_evidence.py --check", text)
        self.assertIn("python tools/normalize_venture_profiles.py --check", text)
        self.assertIn("python tools/stabilize_venture_profiles.py --check", text)
        self.assertNotIn("python tools/normalize_venture_profiles.py\n", text)
        self.assertNotIn("python tools/stabilize_venture_profiles.py\n", text)

    def test_profiles_are_only_committed_after_shared_fixed_point_validation(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        publication_check = text.index(
            "python tools/stabilize_venture_publication_pipeline.py --check"
        )
        validation = text.index("python tools/crawl_venture_profiles.py --validate-only")
        commit = text.index('git commit -m "data: process queued company profile refreshes"')
        self.assertLess(publication_check, commit)
        self.assertLess(validation, commit)


if __name__ == "__main__":
    unittest.main()
