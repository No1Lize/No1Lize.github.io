import unittest

from tools import expand_tracking_entities as expander
from tools import enrich_tracking_people_from_sample_companies as people


class TrackingDiscoveryQualityV2Tests(unittest.TestCase):
    def test_repeated_person_name_is_collapsed(self):
        self.assertEqual(
            people.normalize_person_name("Brandon Tseng Brandon Tseng"),
            "Brandon Tseng",
        )
        self.assertEqual(
            people.person_name_key("Brandon Tseng Brandon Tseng"),
            people.person_name_key("Brandon Tseng"),
        )

    def test_core_team_uses_collapsed_person_name(self):
        profile = {"team": [
            {"name": "Brandon Tseng Brandon Tseng", "role": "联合创始人"},
            {"name": "Brandon Tseng", "role": "CEO"},
        ]}
        names = [item.name for item in people.choose_core_team(profile, "Example")]
        self.assertEqual(names, ["Brandon Tseng"])

    def test_generic_action_words_are_rejected(self):
        self.assertEqual(expander.validate_keyword("Build"), "")
        self.assertEqual(expander.validate_keyword("Release"), "")
        self.assertEqual(expander.validate_keyword("Microsoft"), "Microsoft")


if __name__ == "__main__":
    unittest.main()
