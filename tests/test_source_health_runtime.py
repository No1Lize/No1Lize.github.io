from __future__ import annotations

import unittest

from tools.source_health_runtime import (
    publication_quarantine_ids,
    withhold_quarantined_publication,
)


class SourceHealthRuntimeTests(unittest.TestCase):
    def test_only_configured_grades_and_states_are_quarantined(self) -> None:
        state = {
            "sources": {
                "media-c": {
                    "evidenceGrade": "C",
                    "collectionState": "quarantined",
                },
                "lead-d": {
                    "evidenceGrade": "D",
                    "collectionState": "probation",
                },
                "official-b": {
                    "evidenceGrade": "B",
                    "collectionState": "quarantined",
                },
                "active-c": {
                    "evidenceGrade": "C",
                    "collectionState": "active",
                },
            }
        }
        policy = {"quarantineGrades": ["C", "D"]}
        self.assertEqual(
            publication_quarantine_ids(state, policy),
            {"media-c", "lead-d"},
        )

    def test_withheld_sources_keep_probe_status_but_do_not_replace_history(self) -> None:
        incoming = [
            {"id": "a", "sourceId": "media-c"},
            {"id": "b", "sourceId": "official-b"},
        ]
        statuses = [
            {"id": "media-c", "status": "ok", "accepted": 2},
            {"id": "official-b", "status": "ok", "accepted": 1},
        ]
        publishable, replacement_statuses = withhold_quarantined_publication(
            incoming,
            statuses,
            {"media-c"},
        )
        self.assertEqual([item["id"] for item in publishable], ["b"])
        self.assertEqual(
            [item["id"] for item in replacement_statuses],
            ["official-b"],
        )
        self.assertTrue(statuses[0]["publicationWithheld"])
        self.assertEqual(statuses[0]["collectionState"], "probation")


if __name__ == "__main__":
    unittest.main()
