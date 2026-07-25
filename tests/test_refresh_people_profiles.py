import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_people_profiles", ROOT / "tools" / "refresh_people_profiles.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PeopleProfilePipelineTest(unittest.TestCase):
    def setUp(self):
        self.tracking = json.loads((ROOT / "config" / "user_tracking.json").read_text(encoding="utf-8"))
        self.overrides = json.loads((ROOT / "config" / "person_profile_overrides.json").read_text(encoding="utf-8"))

    def test_tracking_labels_parse_names_and_handles(self):
        self.assertEqual(MODULE.parse_tracking_label("埃隆·马斯克 @elonmusk"), ("埃隆·马斯克", "elonmusk"))
        self.assertEqual(MODULE.parse_tracking_label("Sam Altman"), ("Sam Altman", ""))

    def test_organization_accounts_are_not_people(self):
        people, excluded = MODULE.collect_candidates(self.tracking, self.overrides)
        names = {item["name"] for item in people}
        self.assertIn("Sam Altman", names)
        self.assertIn("王兴兴", names)
        self.assertIn("Michl Binderbauer", names)
        self.assertNotIn("OpenAI", names)
        self.assertNotIn("Anthropic", names)
        self.assertTrue(any("OpenAI" in item for item in excluded))
        self.assertTrue(any("Washington Post" in item for item in excluded))

    def test_same_person_merges_multiple_sectors(self):
        tracking = {
            "tracks": [
                {"name": "AI / AGI", "enabled": True, "people": ["埃隆·马斯克 @elonmusk"]},
                {"name": "商业航天", "enabled": True, "people": ["Elon Musk"]},
            ]
        }
        people, _ = MODULE.collect_candidates(tracking, self.overrides)
        musk = next(item for item in people if item["slug"] == "elon-musk")
        self.assertEqual(set(musk["sectors"]), {"AI / AGI", "商业航天"})
        self.assertIn("elonmusk", musk["handles"])

    def test_offline_generation_keeps_every_real_tracked_person(self):
        payload = MODULE.build_payload(offline=True, workers=1)
        self.assertGreaterEqual(payload["personCount"], 15)
        for person in payload["people"]:
            self.assertTrue(person["slug"])
            self.assertTrue(person["name"])
            self.assertTrue(person["sectors"])
            self.assertTrue(person["materials"])


if __name__ == "__main__":
    unittest.main()
