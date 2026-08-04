from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "publish-validated-data.yml"


class PublishValidatedDataWorkflowTests(unittest.TestCase):
    def test_all_active_scheduled_data_writers_are_watched(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        expected = (
            "Refresh public intelligence every two hours",
            "Refresh public intelligence",
            "Refresh venture profiles",
            "Refresh all listed-company research PDFs",
            "Refresh institution rankings",
            "Refresh STAR Market investors",
            "Monthly source performance review",
        )
        for workflow_name in expected:
            self.assertIn(f"- {workflow_name}", text)
        self.assertNotIn("- Pages", text)
        self.assertNotIn("- Publish validated data updates", text)

    def test_only_successful_main_writer_runs_dispatch_pages(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("github.event.workflow_run.head_branch == 'main'", text)
        self.assertIn("github.event_name == 'workflow_dispatch'", text)
        self.assertEqual(text.count("gh workflow run pages.yml --ref main"), 1)

    def test_dispatch_has_required_permissions_and_fifo(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("contents: read", text)
        self.assertIn("actions: write", text)
        self.assertIn("group: vciq-pages-dispatch", text)
        self.assertIn("queue: max", text)
        self.assertIn('GH_TOKEN: ${{ github.token }}', text)

    def test_publisher_has_no_push_or_schedule_trigger(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("workflow_run:", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("\n  push:\n", text)
        self.assertNotIn("\n  schedule:\n", text)


if __name__ == "__main__":
    unittest.main()
