from __future__ import annotations

import unittest

from tools.semantic_data_diff import semantic_equal


class SemanticDataDiffTest(unittest.TestCase):
    def test_refresh_only_metadata_is_ignored(self) -> None:
        previous = {
            "generatedAt": "2026-07-28T00:00:00Z",
            "refreshAudit": {"completedAt": "old", "newArticleCount": 12},
            "articles": [{"id": "a", "title": "same", "updatedAt": "old"}],
            "sourceStatus": [{"id": "source", "status": "ok", "lastAttemptAt": "old"}],
        }
        current = {
            "generatedAt": "2026-07-29T00:00:00Z",
            "refreshAudit": {"completedAt": "new", "newArticleCount": 0},
            "articles": [{"id": "a", "title": "same", "updatedAt": "new"}],
            "sourceStatus": [{"id": "source", "status": "ok", "lastAttemptAt": "new"}],
        }
        self.assertTrue(semantic_equal(previous, current))

    def test_article_content_change_is_detected(self) -> None:
        previous = {"articles": [{"id": "a", "title": "old"}]}
        current = {"articles": [{"id": "a", "title": "new"}]}
        self.assertFalse(semantic_equal(previous, current))

    def test_source_health_change_is_detected(self) -> None:
        previous = {
            "generatedAt": "old",
            "sources": {"wechat": {"consecutiveFailures": 2, "alertActive": False}},
        }
        current = {
            "generatedAt": "new",
            "sources": {"wechat": {"consecutiveFailures": 3, "alertActive": True}},
        }
        self.assertFalse(semantic_equal(previous, current))


if __name__ == "__main__":
    unittest.main()
