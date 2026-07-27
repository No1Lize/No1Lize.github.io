import unittest

from tools import expand_tracking_entities as expander
from tools import enrich_tracking_people_from_sample_companies as people


class TrackingDiscoveryQualityFollowupTests(unittest.TestCase):
    def test_short_mixed_case_headline_fragment_is_rejected(self):
        self.assertEqual(expander.validate_keyword("Don"), "")
        self.assertEqual(expander.validate_keyword("RAG"), "RAG")

    def test_person_titles_are_canonicalized_for_deduplication(self):
        self.assertEqual(
            people.person_name_key("楼天城博士"),
            people.person_name_key("楼天城"),
        )

    def test_truncated_role_fragment_is_not_a_person(self):
        self.assertFalse(people.is_likely_person_name("同創業者兼"))

    def test_core_team_normalizes_titles_and_rejects_role_fragments(self):
        profile = {
            "team": [
                {"name": "楼天城博士", "role": "联合创始人兼 CEO"},
                {"name": "同創業者兼", "role": "联合创始人"},
                {"name": "Chris Urmson", "role": "CEO"},
            ]
        }
        names = [item.name for item in people.choose_core_team(profile, "Example")]
        self.assertEqual(names, ["楼天城", "Chris Urmson"])


if __name__ == "__main__":
    unittest.main()
