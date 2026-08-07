from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "company-candidate-discovery.yml"
REFRESH_WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"
PRIVATE_CANDIDATE_QUEUE = "config/company_candidate_review_queue.json"


class EntityResolutionWorkflowTests(unittest.TestCase):
    def test_candidate_workflow_reconciles_before_candidate_generation(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        reconcile = text.index("python tools/reconcile_entity_resolution.py")
        build = text.index("python tools/build_resolved_company_candidates.py")
        self.assertLess(reconcile, build)
        self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
        self.assertIn("python tools/build_resolved_company_candidates.py", text)
        self.assertIn(f"--output {PRIVATE_CANDIDATE_QUEUE}", text)
        self.assertIn("--check", text)

    def test_candidate_workflow_commits_reconciled_inputs_and_tracks_scope_changes(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("config/user_tracking.json", text)
        self.assertIn("config/tracking_capture_inbox.json", text)
        self.assertIn(PRIVATE_CANDIDATE_QUEUE, text)
        self.assertNotIn("public/data/company_candidates.json", text)
        self.assertIn("actions: write", text)
        self.assertIn("git diff-tree --no-commit-id --name-only -r HEAD -- config/user_tracking.json", text)
        self.assertIn(
            "git diff-tree --no-commit-id --name-only -r HEAD -- config/company_candidate_review_queue.json",
            text,
        )

    def test_tracking_changes_refresh_snapshot_before_pages_deploy(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        refresh = text.index("gh workflow run scheduled-sync.yml --ref main")
        deploy = text.index("gh workflow run pages.yml --ref main")
        self.assertLess(refresh, deploy)
        self.assertIn("TRACKING_CHANGED: ${{ steps.publish.outputs.tracking_changed }}", text)
        self.assertIn("PUSH_TRACKING_INPUTS_CHANGED: ${{ steps.push-inputs.outputs.changed }}", text)
        self.assertIn("Detect pushed tracking inputs", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertIn("github.event_name == 'push'", text)

    def test_candidate_changes_continue_to_reviewed_onboarding(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("CANDIDATE_CHANGED: ${{ steps.publish.outputs.candidate_changed }}", text)
        self.assertIn("gh workflow run company-candidate-onboarding.yml --ref main", text)

    def test_full_refresh_explicitly_hands_off_to_reconciliation(self) -> None:
        refresh = REFRESH_WORKFLOW.read_text(encoding="utf-8")
        candidate = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Continue through entity reconciliation before publication", refresh)
        self.assertIn("steps.data-update.outcome == 'success'", refresh)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", refresh)
        self.assertIn("workflow_dispatch:", candidate)
        self.assertNotIn("workflow_run:", candidate)
        self.assertIn("gh workflow run pages.yml --ref main", candidate)

    def test_candidate_writer_is_serialized_without_recursive_workflow_run_logic(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("workflow_run:", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_pages_build_uses_the_same_resolution_gate(self) -> None:
        text = PAGES_WORKFLOW.read_text(encoding="utf-8")
        reconcile = text.index("python tools/reconcile_entity_resolution.py")
        build = text.index("python tools/build_resolved_company_candidates.py")
        self.assertLess(reconcile, build)
        self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
        self.assertIn("python tools/build_resolved_company_candidates.py", text)
        self.assertIn("--check", text)


if __name__ == "__main__":
    unittest.main()
