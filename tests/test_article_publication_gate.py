from __future__ import annotations

import unittest

from tools import article_publication_gate as gate


class ArticlePublicationGateTests(unittest.TestCase):
    @staticmethod
    def article(**overrides) -> dict:
        row = {
            "id": "a",
            "sourceId": "source-a",
            "title": "OpenAI 发布新模型",
            "summary": "OpenAI 发布新模型并公布能力更新。",
            "type": "产品发布",
            "company": "OpenAI",
            "companySlug": "openai",
            "publishedAt": "2026-08-08",
            "source": {
                "url": "https://example.com/a",
                "evidenceGrade": "D",
                "sourceRole": "discovery",
            },
        }
        row.update(overrides)
        return row

    def test_primary_and_corroboration_are_not_restricted(self) -> None:
        primary = self.article(
            id="primary",
            source={"url": "https://openai.com/news/a", "sourceRole": "primary"},
        )
        media = self.article(
            id="media",
            source={"url": "https://techcrunch.com/a", "sourceRole": "corroboration"},
        )
        published, report = gate.filter_publishable_articles([primary, media])
        self.assertEqual([row["id"] for row in published], ["primary", "media"])
        self.assertEqual(report["primary"], 1)
        self.assertEqual(report["corroboration"], 1)

    def test_discovery_without_concrete_entity_is_held(self) -> None:
        row = self.article(company="科技产业", companySlug="", title="AI 行业发布新进展")
        published, report = gate.filter_publishable_articles([row])
        self.assertEqual(published, [])
        self.assertEqual(report["discoveryHeld"], 1)

    def test_discovery_with_generic_event_is_held(self) -> None:
        row = self.article(type="公司动态", qualityScore=90)
        published, _ = gate.filter_publishable_articles([row])
        self.assertEqual(published, [])

    def test_relevant_discovery_with_entity_and_event_is_publishable(self) -> None:
        row = self.article(qualityScore=58)
        published, report = gate.filter_publishable_articles([row])
        self.assertEqual(len(published), 1)
        self.assertEqual(report["discoveryPublished"], 1)

    def test_low_score_discovery_can_be_confirmed_by_independent_primary_source(self) -> None:
        primary = self.article(
            id="primary",
            sourceId="official-openai",
            source={"url": "https://openai.com/news/model", "sourceRole": "primary"},
        )
        discovery = self.article(
            id="discovery",
            sourceId="search-index",
            qualityScore=10,
            title="模型发布事件",
            source={"url": "https://example.net/story", "sourceRole": "discovery"},
        )
        published, _ = gate.filter_publishable_articles([primary, discovery])
        self.assertEqual({row["id"] for row in published}, {"primary", "discovery"})

    def test_same_source_does_not_self_corroborate(self) -> None:
        primary = self.article(
            id="primary",
            sourceId="same-source",
            source={"url": "https://example.com/official", "sourceRole": "primary"},
        )
        discovery = self.article(
            id="discovery",
            sourceId="same-source",
            qualityScore=10,
            title="模型发布事件",
            source={"url": "https://example.com/other", "sourceRole": "discovery"},
        )
        published, _ = gate.filter_publishable_articles([primary, discovery])
        self.assertEqual([row["id"] for row in published], ["primary"])


if __name__ == "__main__":
    unittest.main()
