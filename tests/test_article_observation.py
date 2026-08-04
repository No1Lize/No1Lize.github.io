import unittest

from tools.article_observation import (
    apply_incoming_observations,
    prepare_existing_articles,
    validate_observation_metadata,
)


class ArticleObservationTests(unittest.TestCase):
    def test_new_article_gets_exact_first_seen_and_last_verified(self):
        incoming = [
            {
                "id": "article-new",
                "publishedAt": "2026-08-03",
                "source": {"url": "https://example.com/story?utm_source=test"},
            }
        ]
        result = apply_incoming_observations(
            [], incoming, "2026-08-04T00:15:00+00:00"
        )[0]
        self.assertEqual(result["firstSeenAt"], "2026-08-04T00:15:00+00:00")
        self.assertEqual(result["lastVerifiedAt"], "2026-08-04T00:15:00+00:00")
        self.assertFalse(result["firstSeenEstimated"])
        self.assertFalse(result["lastVerifiedEstimated"])

    def test_existing_article_preserves_first_seen_and_refreshes_verification(self):
        existing = [
            {
                "id": "article-existing",
                "firstSeenAt": "2026-07-30T10:00:00Z",
                "firstSeenEstimated": False,
                "lastVerifiedAt": "2026-08-01T10:00:00Z",
                "source": {"url": "https://example.com/story"},
            }
        ]
        incoming = [
            {
                "id": "article-existing",
                "source": {"url": "https://example.com/story?utm_campaign=again"},
            }
        ]
        result = apply_incoming_observations(
            existing, incoming, "2026-08-04T01:00:00Z"
        )[0]
        self.assertEqual(result["firstSeenAt"], "2026-07-30T10:00:00+00:00")
        self.assertEqual(result["lastVerifiedAt"], "2026-08-04T01:00:00+00:00")
        self.assertFalse(result["firstSeenEstimated"])

    def test_url_identity_survives_tracking_parameter_changes(self):
        existing = [
            {
                "id": "legacy-id",
                "firstSeenAt": "2026-07-20T00:00:00+00:00",
                "source": {"url": "https://example.com/story?utm_source=old&x=1"},
            }
        ]
        incoming = [
            {
                "id": "new-id",
                "source": {"url": "https://example.com/story?x=1&utm_source=new"},
            }
        ]
        result = apply_incoming_observations(
            existing, incoming, "2026-08-04T02:00:00+00:00"
        )[0]
        self.assertEqual(result["firstSeenAt"], "2026-07-20T00:00:00+00:00")

    def test_legacy_rows_use_snapshot_upper_bound_and_are_estimated(self):
        result = prepare_existing_articles(
            [
                {
                    "id": "legacy",
                    "publishedAt": "2026-07-01",
                    "source": {"url": "https://example.com/legacy"},
                }
            ],
            "2026-08-03T12:00:00Z",
        )[0]
        self.assertEqual(result["firstSeenAt"], "2026-08-03T12:00:00+00:00")
        self.assertEqual(result["lastVerifiedAt"], "2026-08-03T12:00:00+00:00")
        self.assertTrue(result["firstSeenEstimated"])
        self.assertTrue(result["lastVerifiedEstimated"])

    def test_validation_rejects_reversed_observation_order(self):
        errors = validate_observation_metadata(
            {
                "firstSeenAt": "2026-08-04T10:00:00Z",
                "lastVerifiedAt": "2026-08-04T09:00:00Z",
            }
        )
        self.assertIn("invalid:observation-order", errors)


if __name__ == "__main__":
    unittest.main()
