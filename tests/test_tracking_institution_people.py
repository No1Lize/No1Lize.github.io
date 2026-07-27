import unittest

from tools.enrich_tracking_institutions import (
    choose_institution_team,
    enrich_config,
    institution_rows,
    sync_sample_institutions,
)
from tools.enrich_tracking_people_from_sample_companies import (
    PublicWikidataClient,
    empty_ledger,
)


class TrackingInstitutionPeopleTests(unittest.TestCase):
    def setUp(self):
        self.track = {
            "slug": "track-vc",
            "name": "风险投资",
            "enabled": True,
            "custom": True,
            "keywords": ["私人股权投资", "天使轮"],
            "people": [],
            "sampleCompanies": ["Example Ventures"],
        }
        self.config = {
            "schemaVersion": 1,
            "tracks": [self.track],
            "listedCompanies": [],
            "sources": [],
        }
        self.venture = {
            "institutions": {
                "example-ventures": {
                    "slug": "example-ventures",
                    "name": "Example Ventures",
                    "team": [
                        {
                            "name": "Alice Chen",
                            "role": "创始管理合伙人",
                            "sourceUrl": "https://example.vc/team",
                        },
                        {
                            "name": "Bob Li",
                            "role": "合伙人",
                            "sourceUrl": "https://example.vc/team",
                        },
                        {
                            "name": "Carol Wu",
                            "role": "投资总监",
                            "sourceUrl": "https://example.vc/team",
                        },
                        {
                            "name": "Press Team",
                            "role": "媒体团队",
                            "sourceUrl": "https://example.vc/team",
                        },
                    ],
                },
                "second-capital": {
                    "slug": "second-capital",
                    "name": "Second Capital",
                    "team": [],
                },
            }
        }

    def test_institution_rows_read_the_shared_profile_snapshot(self):
        rows = institution_rows(self.venture)
        self.assertEqual([row["name"] for row in rows], ["Example Ventures", "Second Capital"])

    def test_institution_team_prioritizes_partners(self):
        candidates = choose_institution_team(
            self.venture["institutions"]["example-ventures"],
            "Example Ventures",
        )
        self.assertEqual([item.name for item in candidates], ["Alice Chen", "Bob Li", "Carol Wu"])

    def test_sample_institutions_are_reused_without_duplicates(self):
        added = sync_sample_institutions(
            self.track,
            institution_rows(self.venture),
            empty_ledger(),
        )
        self.assertEqual(added, ["Second Capital"])
        self.assertEqual(self.track["sampleCompanies"].count("Example Ventures"), 1)

    def test_removed_auto_institution_is_not_reintroduced(self):
        ledger = empty_ledger()
        ledger["removed"].append(
            {
                "track": "track-vc",
                "kind": "sampleCompanies",
                "value": "Second Capital",
                "removedAt": "2026-07-27T00:00:00+00:00",
            }
        )
        added = sync_sample_institutions(self.track, institution_rows(self.venture), ledger)
        self.assertEqual(added, [])
        self.assertNotIn("Second Capital", self.track["sampleCompanies"])

    def test_enrichment_adds_people_and_exact_team_page_source(self):
        result = enrich_config(
            self.config,
            self.venture,
            {"people": []},
            empty_ledger(),
            PublicWikidataClient(max_requests=0),
        )
        self.assertTrue(result["changed"])
        self.assertEqual(self.track["people"], ["Alice Chen", "Bob Li", "Carol Wu"])
        team_sources = [
            source for source in self.config["sources"]
            if source["url"] == "https://example.vc/team"
        ]
        self.assertEqual(len(team_sources), 1)
        self.assertEqual(team_sources[0]["sourceCategory"], "person")
        self.assertEqual(team_sources[0]["company"], "Example Ventures")
        self.assertIn("Alice Chen", team_sources[0]["keywords"])


if __name__ == "__main__":
    unittest.main()
