from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "company-candidate-discovery.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class EntityResolutionWorkflowTests(unittest.TestCase):
    def test_candidate_workflow_reconciles_before_candidate_generation(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        reconcile = text.index("python tools/reconcile_entity_resolution.py")
        build = text.index("python tools/build_resolved_company_candidates.py")
        self.assertLess(reconcile, build)
        self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
        self.assertIn("python tools/build_resolved_company_candidates.py --check", text)
        self.assertNotIn("python tools/build_company_candidates.py\n", text)

    def test_candidate_workflow_commits_reconciled_inputs_and_deploys(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("config/user_tracking.json", text)
        self.assertIn("config/tracking_capture_inbox.json", text)
        self.assertIn("public/data/company_candidates.json", text)
        self.assertIn("actions: write", text)
        self.assertIn("gh workflow run pages.yml --ref main", text)

    def test_candidate_generation_follows_successful_full_refreshes(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('workflows: ["Refresh public intelligence"]', text)
        self.assertIn("types: [completed]", text)
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn("ref: main", text)

    def test_failed_refreshes_skip_outside_the_writer_queue(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event_name == 'workflow_run'", text)
        self.assertIn("github.event.workflow_run.conclusion != 'success'", text)
        self.assertIn("vciq-company-candidate-skip-{0}", text)
        self.assertIn("github.run_id", text)
        self.assertIn("vciq-repository-writer-{0}", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("queue: single", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_pages_build_uses_the_same_resolution_gate(self) -> None:
        text = PAGES_WORKFLOW.read_text(encoding="utf-8")
        reconcile = text.index("python tools/reconcile_entity_resolution.py")
        build = text.index("python tools/build_resolved_company_candidates.py")
        self.assertLess(reconcile, build)
        self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
        self.assertIn("python tools/build_resolved_company_candidates.py --check", text)
        self.assertNotIn("python tools/build_company_candidates.py\n", text)


if __name__ == "__main__":
    unittest.main()
