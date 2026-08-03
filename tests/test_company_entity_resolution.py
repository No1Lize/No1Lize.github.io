from __future__ import annotations

import unittest

from tools.resolve_company_entities import build_registry, resolve_article, resolve_payload


REGISTRY = build_registry(
    {
        "companies": [
            {
                "slug": "openai",
                "name": "OpenAI",
                "homepage": "https://openai.com/about/",
                "newsUrls": ["https://openai.com/news/"],
                "aliases": ["ChatGPT"],
            },
            {
                "slug": "bytedance",
                "name": "字节跳动",
                "homepage": "https://www.bytedance.com/zh/",
                "aliases": ["ByteDance"],
            },
            {
                "slug": "meta",
                "name": "Meta",
                "homepage": "https://about.meta.com/",
                "aliases": [],
            },
            {
                "slug": "scale-ai",
                "name": "Scale AI",
                "homepage": "https://scale.com/",
                "aliases": ["Scale"],
            },
        ]
    }
)


def article(**overrides):
    payload = {
        "id": "a-1",
        "title": "行业动态",
        "summary": "公开市场信息",
        "company": "科技产业",
        "source": {"name": "媒体", "url": "https://example.com/story"},
    }
    payload.update(overrides)
    return payload


class CompanyEntityResolutionTests(unittest.TestCase):
    def test_explicit_slug_is_publishable(self):
        resolved, changed = resolve_article(article(companySlug="openai"), REGISTRY)
        self.assertTrue(changed)
        self.assertEqual(resolved["companySlugs"], ["openai"])
        self.assertEqual(resolved["companyMatch"]["method"], "explicit-slug")
        self.assertEqual(resolved["company"], "OpenAI")

    def test_official_domain_is_publishable(self):
        resolved, _ = resolve_article(
            article(source={"name": "OpenAI", "url": "https://openai.com/news/product"}),
            REGISTRY,
        )
        self.assertEqual(resolved["companySlugs"], ["openai"])
        self.assertEqual(resolved["companyMatch"]["method"], "official-domain")

    def test_exact_structured_company_is_publishable(self):
        resolved, _ = resolve_article(article(company="ByteDance"), REGISTRY)
        self.assertEqual(resolved["companySlugs"], ["bytedance"])
        self.assertEqual(resolved["companyMatch"]["method"], "structured-company")

    def test_multiple_structured_mentions_are_preserved(self):
        resolved, _ = resolve_article(
            article(mentionedCompanies=["OpenAI", "字节跳动"]),
            REGISTRY,
        )
        self.assertEqual(resolved["companySlugs"], ["openai", "bytedance"])
        self.assertEqual(len(resolved["companyMatches"]), 2)

    def test_free_text_mentions_are_candidates_only(self):
        resolved, _ = resolve_article(
            article(
                title="OpenAI 与 Scale AI 发布新的合作计划",
                summary="两家公司公布了进一步合作安排。",
            ),
            REGISTRY,
        )
        self.assertNotIn("companySlugs", resolved)
        self.assertEqual(resolved["companyCandidateSlugs"], ["openai", "scale-ai"])

    def test_short_ambiguous_names_are_not_text_candidates(self):
        resolved, _ = resolve_article(
            article(title="Meta 与 Scale 相关指标上升", summary="行业统计口径更新。"),
            REGISTRY,
        )
        self.assertNotIn("companySlugs", resolved)
        self.assertNotIn("companyCandidateSlugs", resolved)

    def test_payload_resolution_is_idempotent(self):
        payload = {"articles": [article(company="OpenAI")], "articleCount": 1}
        first, first_report = resolve_payload(payload, REGISTRY)
        second, second_report = resolve_payload(first, REGISTRY)
        self.assertEqual(first_report["changedArticles"], 1)
        self.assertEqual(second_report["changedArticles"], 0)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
