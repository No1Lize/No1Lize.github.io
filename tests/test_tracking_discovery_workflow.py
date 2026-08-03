from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "tracking-discovery.yml"


class TrackingDiscoveryWorkflowTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
