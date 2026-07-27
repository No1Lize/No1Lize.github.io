from __future__ import annotations

import unittest

from tools.refine_eastmoney_snapshot import (
    is_relevant_eastmoney_article,
    is_roundup_title,
    refine_snapshot,
)


DETAIL_BASE = "https://finance.eastmoney.com/a/20260725"


def eastmoney_article(
    article_id: str,
    title: str,
    summary: str,
    *,
    company: str = "科技产业",
    sector: str = "AI / AGI",
) -> dict:
    return {
        "id": article_id,
        "sourceId": "official-user-东方财富",
        "title": title,
        "summary": summary,
        "type": "公司动态",
        "region": "中国",
        "sector": sector,
        "company": company,
        "publishedAt": "2026-07-25",
        "importance": 80,
        "source": {
            "name": "东方财富",
            "url": f"{DETAIL_BASE}{article_id[-6:]}.html",
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }


class EastmoneyRefinementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tracking = {
            "listedCompanies": [
                {
                    "id": "catalog-catl",
                    "name": "宁德时代",
                    "ticker": "300750",
                    "market": "A股",
                    "sector": "新能源",
                    "enabled": True,
                    "catalogSlug": "catl",
                },
                {
                    "id": "catalog-cambricon",
                    "name": "寒武纪",
                    "ticker": "688256",
                    "market": "A股",
                    "sector": "半导体",
                    "enabled": True,
                    "catalogSlug": "cambricon",
                },
            ]
        }

    def test_roundup_titles_are_rejected_even_when_a_company_was_attributed(self) -> None:
        article = eastmoney_article(
            "roundup-000001",
            "7月24日东方财富财经晚报（附新闻联播）",
            "宁德时代发布半年报，随后还汇总了监管、宏观和市场新闻。",
            company="宁德时代",
            sector="新能源",
        )
        self.assertTrue(is_roundup_title(article["title"]))
        relevant, reason = is_relevant_eastmoney_article(article, {"宁德时代"})
        self.assertFalse(relevant)
        self.assertEqual(reason, "roundup")

    def test_unrelated_social_news_is_rejected(self) -> None:
        article = eastmoney_article(
            "social-000002",
            "英国一处工业区发生火灾和爆炸",
            "当地消防部门派出人员处置，事故原因仍在调查。",
            sector="智能制造",
        )
        relevant, reason = is_relevant_eastmoney_article(article, {"宁德时代"})
        self.assertFalse(relevant)
        self.assertEqual(reason, "unrelated")

    def test_real_tracked_company_news_is_kept(self) -> None:
        article = eastmoney_article(
            "company-000003",
            "宁德时代发布新一代固态电池研发进展",
            "宁德时代表示产品已进入中试验证阶段。",
            company="宁德时代",
            sector="新能源",
        )
        relevant, reason = is_relevant_eastmoney_article(article, {"宁德时代"})
        self.assertTrue(relevant)
        self.assertEqual(reason, "tracked-company")

    def test_generic_but_focused_technology_news_is_kept(self) -> None:
        article = eastmoney_article(
            "technology-000004",
            "国产AI芯片进入新一轮客户验证",
            "新一代算力芯片面向大模型推理负载提升能效。",
            sector="半导体",
        )
        relevant, reason = is_relevant_eastmoney_article(article, set())
        self.assertTrue(relevant)
        self.assertEqual(reason, "technology-title")

    def test_snapshot_counts_and_source_status_follow_refined_articles(self) -> None:
        other = {
            "id": "other-source",
            "sourceId": "anthropic",
            "title": "Anthropic publishes a model update",
            "company": "Anthropic",
            "source": {
                "name": "Anthropic",
                "url": "https://www.anthropic.com/news/model-update",
            },
        }
        snapshot = {
            "articleCount": 5,
            "articles": [
                other,
                eastmoney_article(
                    "roundup-000001",
                    "7月24日东方财富财经晚报（附新闻联播）",
                    "宁德时代发布半年报，同时汇总多条市场信息。",
                    company="宁德时代",
                    sector="新能源",
                ),
                eastmoney_article(
                    "social-000002",
                    "英国一处工业区发生火灾和爆炸",
                    "消防部门正在调查事故原因。",
                    sector="智能制造",
                ),
                eastmoney_article(
                    "company-000003",
                    "宁德时代发布新一代固态电池研发进展",
                    "宁德时代表示产品已进入中试验证阶段。",
                    company="宁德时代",
                    sector="新能源",
                ),
                eastmoney_article(
                    "technology-000004",
                    "国产AI芯片进入新一轮客户验证",
                    "新一代算力芯片面向大模型推理负载提升能效。",
                    sector="半导体",
                ),
            ],
            "sourceStatus": [
                {
                    "id": "official-user-东方财富",
                    "name": "东方财富",
                    "status": "ok",
                    "accepted": 4,
                }
            ],
        }

        refined, report = refine_snapshot(snapshot, self.tracking)

        self.assertEqual(refined["articleCount"], 3)
        self.assertEqual(
            [article["id"] for article in refined["articles"]],
            ["other-source", "company-000003", "technology-000004"],
        )
        self.assertEqual(refined["sourceStatus"][0]["accepted"], 2)
        self.assertEqual(refined["sourceStatus"][0]["status"], "ok")
        self.assertEqual(report["eastmoneySeen"], 4)
        self.assertEqual(report["eastmoneyKept"], 2)
        self.assertEqual(
            report["removedRoundups"],
            ["7月24日东方财富财经晚报（附新闻联播）"],
        )
        self.assertEqual(
            report["removedUnrelated"],
            ["英国一处工业区发生火灾和爆炸"],
        )

    def test_source_status_becomes_empty_when_every_eastmoney_story_is_removed(self) -> None:
        snapshot = {
            "articleCount": 1,
            "articles": [
                eastmoney_article(
                    "roundup-000001",
                    "东方财富财经早报",
                    "今日多条市场新闻汇总。",
                )
            ],
            "sourceStatus": [
                {
                    "id": "official-user-东方财富",
                    "status": "partial",
                    "accepted": 1,
                }
            ],
        }

        refined, report = refine_snapshot(snapshot, self.tracking)

        self.assertEqual(refined["articleCount"], 0)
        self.assertEqual(refined["sourceStatus"][0]["accepted"], 0)
        self.assertEqual(refined["sourceStatus"][0]["status"], "empty")
        self.assertEqual(report["eastmoneyKept"], 0)


if __name__ == "__main__":
    unittest.main()
