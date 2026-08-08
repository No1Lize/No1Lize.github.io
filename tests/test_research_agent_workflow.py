from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "research-agent-v1.yml"
PAGES_WORKFLOW = ROOT / ".github" / "workflows" / "pages.yml"


class ResearchAgentWorkflowTest(unittest.TestCase):
    def test_research_runs_share_the_repository_writer_lock(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)
        self.assertNotIn("queue: single", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_research_generation_is_explicit_dispatch_only(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  workflow_dispatch:", text)
        self.assertNotIn("workflow_run:", text)
        self.assertNotIn('workflows: ["Refresh public intelligence"]', text)
        self.assertNotIn("  push:\n", text)

    def test_terminal_pages_deployment_dispatches_research(self) -> None:
        pages = PAGES_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("run_research_after_deploy:", pages)
        self.assertIn("Continue to Research Agent after terminal publication", pages)
        self.assertIn("inputs.run_research_after_deploy == true", pages)
        self.assertIn("gh workflow run research-agent-v1.yml --ref main", pages)
        self.assertIn("actions: write", pages)

    def test_research_still_validates_runtime_and_control_plane_before_generation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "python -m unittest tests.test_research_agent tests.test_research_agent_workflow",
            text,
        )
        self.assertIn("python -m unittest tests.test_research_agent_runtime", text)
        self.assertIn("python tools/run_pipeline.py check", text)


if __name__ == "__main__":
    unittest.main()
