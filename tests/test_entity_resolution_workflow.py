from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_WORKFLOW = ROOT / ".github" / "workflows" / "company-candidate-discovery.yml"
ONBOARDING_WORKFLOW = ROOT / ".github" / "workflows" / "company-candidate-onboarding.yml"
REFRESH_WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class EntityResolutionWorkflowTests(unittest.TestCase):
    def test_candidate_workflow_reconciles_before_candidate_generation(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        reconcile = text.index("python tools/reconcile_entity_resolution.py")
        build = text.index("python tools/build_resolved_company_candidates.py")
        self.assertLess(reconcile, build)
        self.assertIn("python tools/reconcile_entity_resolution.py --check", text)
        self.assertIn("--output \"$CANDIDATE_QUEUE\"", text)
        self.assertIn("--candidates \"$CANDIDATE_QUEUE\"", text)
        self.assertIn("--check", text)

    def test_candidate_workflow_commits_private_review_state_and_tracks_scope_changes(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("config/user_tracking.json", text)
        self.assertIn("config/tracking_capture_inbox.json", text)
        self.assertIn("config/company_candidate_review_queue.json", text)
        self.assertIn("config/company_candidate_decisions.json", text)
        self.assertNotIn("public/data/company_candidates.json", text)
        self.assertIn("actions: write", text)
        self.assertIn(
            "git diff-tree --no-commit-id --name-only -r HEAD -- config/user_tracking.json",
            text,
        )

    def test_private_candidate_changes_handoff_to_onboarding_without_pages_deploy(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("CANDIDATE_CHANGED: ${{ steps.publish.outputs.candidate_changed }}", text)
        self.assertIn("gh workflow run company-candidate-onboarding.yml --ref main", text)
        self.assertIn("gh workflow run scheduled-sync.yml --ref main", text)
        self.assertNotIn("gh workflow run pages.yml --ref main", text)
        self.assertIn("private review state does not require a Pages deployment", text)

    def test_tracking_changes_refresh_snapshot_before_publication(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        pages = PAGES_WORKFLOW.read_text(encoding="utf-8")
        refresh = REFRESH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("TRACKING_CHANGED: ${{ steps.publish.outputs.tracking_changed }}", text)
        self.assertIn(
            "PUSH_TRACKING_INPUTS_CHANGED: ${{ steps.push-inputs.outputs.changed }}",
            text,
        )
        self.assertIn("Detect pushed tracking inputs", text)
        self.assertIn("gh workflow run scheduled-sync.yml --ref main", text)
        self.assertIn("      - config/user_tracking.json", refresh)
        self.assertIn("      - config/user_tracking.json", pages)

    def test_full_refresh_explicitly_hands_off_to_reconciliation(self) -> None:
        refresh = REFRESH_WORKFLOW.read_text(encoding="utf-8")
        candidate = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("Continue through entity reconciliation before publication", refresh)
        self.assertIn("steps.data-update.outcome == 'success'", refresh)
        self.assertIn("gh workflow run company-candidate-discovery.yml --ref main", refresh)
        self.assertIn("workflow_dispatch:", candidate)
        self.assertNotIn("workflow_run:", candidate)

    def test_candidate_writer_is_serialized_without_recursive_workflow_run_logic(self) -> None:
        text = CANDIDATE_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("workflow_run:", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_onboarding_uses_private_queue_and_state_paths(self) -> None:
        text = ONBOARDING_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("CANDIDATE_QUEUE: config/company_candidate_review_queue.json", text)
        self.assertIn("ONBOARDING_STATE: config/company_candidate_onboarding_state.json", text)
        self.assertIn("--candidates \"$CANDIDATE_QUEUE\"", text)
        self.assertIn("--report \"$ONBOARDING_STATE\"", text)
        self.assertNotIn("public/data/company_candidates.json", text)
        self.assertNotIn("public/data/company_candidate_onboarding.json", text)

    def test_pages_build_does_not_depend_on_private_candidate_fixed_point(self) -> None:
        text = PAGES_WORKFLOW.read_text(encoding="utf-8")
        runtime = text.split("permissions:", 1)[1]
        self.assertIn("python tools/reconcile_entity_resolution.py --check", runtime)
        self.assertNotIn("python tools/apply_manual_company_trust.py", runtime)
        self.assertNotIn("python tools/build_resolved_company_candidates.py", runtime)
        self.assertNotIn("config/company_candidate_review_queue.json", runtime)
        self.assertNotIn("config/company_candidate_onboarding_state.json", runtime)
        self.assertNotIn("public/data/company_candidates.json", runtime)

        self.assertIn("paths-ignore:", text)
        self.assertIn("config/user_tracking.json", text)
        self.assertIn("config/company_candidate_review_queue.json", text)
        self.assertIn("config/company_candidate_onboarding_state.json", text)
        self.assertIn("config/company_candidate_decisions.json", text)
        self.assertIn("config/tracking_capture_inbox.json", text)
        self.assertIn("config/entity_resolution_decisions.json", text)


if __name__ == "__main__":
    unittest.main()
