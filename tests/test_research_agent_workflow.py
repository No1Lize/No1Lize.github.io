from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "research-agent-v1.yml"


class ResearchAgentWorkflowTest(unittest.TestCase):
    def test_only_latest_pending_research_writer_is_retained(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-", text)
        self.assertIn("github.ref", text)
        self.assertIn("queue: single", text)
        self.assertNotIn("queue: max", text)
        self.assertNotIn("cancel-in-progress:", text)

    def test_failed_refreshes_are_filtered_before_generation(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.event.workflow_run.conclusion == 'success'", text)
        self.assertIn("python -m unittest tests.test_research_agent tests.test_research_agent_workflow", text)


if __name__ == "__main__":
    unittest.main()
