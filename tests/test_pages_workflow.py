from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "pages.yml"
CONTROL_PLANE_PATH = ROOT / "tools" / "run_pipeline.py"


class PagesWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        cls.control_plane = CONTROL_PLANE_PATH.read_text(encoding="utf-8")
        cls.lines = [line.strip() for line in cls.workflow.splitlines()]

    def test_pages_build_only_observes_and_validates_committed_data(self):
        python_commands = [
            line for line in self.lines if line.startswith("python tools/")
        ]
        self.assertEqual(
            python_commands,
            [
                "python tools/run_pipeline.py check",
                "python tools/reconcile_entity_resolution.py --check",
                "python tools/build_resolved_company_candidates.py --check",
                "python tools/company_profile_refresh_queue.py --check",
                "python tools/crawl_articles.py --validate-only",
                "python tools/validate_eastmoney_snapshot.py",
                "python tools/run_pipeline.py refresh \\",
                "python tools/run_pipeline.py build-provenance \\",
            ],
        )
        self.assertNotIn("Reconcile derived public data", self.workflow)
        self.assertNotIn("tools/run_pipeline.py finalize", self.workflow)

    def test_pages_build_is_pinned_to_the_event_commit(self):
        self.assertIn("ref: ${{ github.sha }}", self.workflow)
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn('test "$(git rev-parse HEAD)" = "${GITHUB_SHA}"', self.workflow)
        self.assertEqual(
            self.workflow.count("git diff --exit-code -- config public/data"),
            2,
        )

    def test_tracking_coverage_cannot_be_bypassed(self):
        self.assertNotIn("ALLOW_INCOMPLETE_TRACKING_COVERAGE", self.workflow)
        self.assertIn("run: npm run build:pages", self.workflow)

    def test_deployed_artifact_records_source_sha_and_control_plane_hashes(self):
        self.assertIn('"sourceSha": git_head(root)', self.control_plane)
        self.assertIn("--output out/build-provenance.json", self.workflow)
        self.assertIn("--lineage out/data/data_lineage.json", self.workflow)
        self.assertIn("--health out/data/pipeline_health.json", self.workflow)
        self.assertIn("uses: actions/upload-pages-artifact@v3", self.workflow)


if __name__ == "__main__":
    unittest.main()
