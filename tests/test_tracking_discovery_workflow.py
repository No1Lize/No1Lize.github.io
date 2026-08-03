from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tracking-discovery.yml"


class TrackingDiscoveryWorkflowTests(unittest.TestCase):
    def test_discovery_only_runs_on_schedule_or_manual_dispatch(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        trigger_block = text.split("permissions:", 1)[0]
        self.assertIn('cron: "0 3 * * 0"', trigger_block)
        self.assertIn('timezone: "Asia/Taipei"', trigger_block)
        self.assertIn("workflow_dispatch:", trigger_block)
        self.assertNotIn("  push:\n", trigger_block)
        self.assertNotIn("config/user_tracking.json", trigger_block)

    def test_job_has_a_hard_timeout_and_bounded_network_budget(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("timeout-minutes: 45", text)
        self.assertIn("--max-requests 240", text)
        self.assertIn("--max-requests 50", text)
        self.assertIn("--max-requests 70", text)
        self.assertNotIn("--max-requests 420", text)

    def test_mode_is_exported_for_concurrent_replay(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn('echo "mode=$MODE" >> "$GITHUB_OUTPUT"', text)
        self.assertIn('DISCOVERY_MODE: ${{ steps.expand.outputs.mode }}', text)

    def test_push_failure_replays_from_latest_main(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("regenerate_from_latest_main()", text)
        self.assertIn("git fetch origin main", text)
        self.assertIn("git reset --hard origin/main", text)
        self.assertIn("python tools/enrich_tracking_people_from_sample_companies.py", text)
        self.assertIn("python tools/enrich_tracking_person_channels.py", text)
        self.assertIn("python tools/expand_tracking_entities.py", text)
        self.assertIn("npm run validate:tracking", text)
        self.assertIn("npm run validate:taxonomy", text)
        self.assertNotIn("git pull --rebase origin main", text)

    def test_successful_push_relies_on_the_full_refresh_push_trigger(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("if git push origin HEAD:main; then", text)
        self.assertNotIn("gh workflow run scheduled-sync.yml --ref main", text)

    def test_workflow_keeps_the_shared_writer_queue(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("group: vciq-repository-writer-${{ github.ref }}", text)
        self.assertIn("queue: max", text)


if __name__ == "__main__":
    unittest.main()
