from __future__ import annotations

import copy
import unittest

from tools.enrich_venture_profiles import enrich_snapshot


CATALOG = '''
export const companies = [
{ slug:"openai", name:"OpenAI", englishName:"OpenAI", region:"美国", sector:"AI / AGI", stage:"成长期", status:"运营中", headquarters:"旧金山", founded:"2015", summary:"研发并商业化通用人工智能模型与开发者平台。", product:"GPT 模型、ChatGPT 与 API", source:official("OpenAI","https://openai.com/") },
];
export type Institution = {};
export const institutionCatalog = [
{ slug:"sequoia", name:"Sequoia Capital", englishName:"Sequoia Capital", region:"美国", type:"风险投资", stages:"全阶段", sectors:["AI","企业科技"], source:official("Sequoia Capital","https://www.sequoiacap.com/") },
];
export type IpoCompany = {};
'''


class VentureProfileEnrichmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = {
            "schemaVersion": 1,
            "generatedAt": "2026-07-25T12:00:00+00:00",
            "companies": {
                "openai": {
                    "slug": "openai",
                    "name": "OpenAI",
                    "updatedAt": "2026-07-25T11:00:00+00:00",
                    "status": "partial",
                    "background": "首页 关于我们 产品中心 新闻资讯 联系我们 加入我们 " * 20,
                    "technology": "GPT 模型采用大规模训练与推理基础设施，为开发者和企业提供模型能力。",
                    "products": ["GPT 模型", "ChatGPT", "API"],
                    "team": [
                        {
                            "name": "Sam Altman",
                            "role": "CEO",
                            "summary": "",
                            "sourceUrl": "https://openai.com/about/",
                        }
                    ],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [
                        {
                            "name": "OpenAI",
                            "url": "https://openai.com/",
                            "level": "官方披露",
                        }
                    ],
                    "warnings": [],
                    "evidenceScore": 40,
                }
            },
            "institutions": {
                "sequoia": {
                    "slug": "sequoia",
                    "name": "Sequoia Capital",
                    "updatedAt": "2026-07-25T11:00:00+00:00",
                    "status": "partial",
                    "overview": "Sequoia Capital is a venture capital firm.",
                    "strategy": "The firm invests across stages in technology companies.",
                    "team": [],
                    "recentInvestments": [],
                    "portfolio": [],
                    "classicCases": [],
                    "sources": [
                        {
                            "name": "Sequoia Capital",
                            "url": "https://www.sequoiacap.com/",
                            "level": "官方披露",
                        }
                    ],
                    "warnings": [],
                    "evidenceScore": 30,
                }
            },
            "sourceStatus": [],
            "qualityGate": {
                "passed": True,
                "checks": {
                    "companyCoverage": {"actual": 1, "required": 1, "passed": True},
                    "institutionCoverage": {"actual": 1, "required": 1, "passed": True},
                },
            },
        }
        self.articles = {
            "articles": [
                {
                    "id": "openai-funding",
                    "company": "OpenAI",
                    "companySlug": "openai",
                    "title": "OpenAI完成新一轮融资",
                    "summary": "OpenAI完成新一轮融资，Sequoia Capital参与投资，资金将用于模型训练和企业部署。",
                    "type": "融资",
                    "sector": "AI / AGI",
                    "publishedAt": "2026-04-10",
                    "institutions": ["Sequoia Capital"],
                    "source": {"url": "https://example.com/openai-funding"},
                },
                {
                    "id": "infinity-funding",
                    "company": "Infinity",
                    "companySlug": "infinity",
                    "title": "Infinity raises a new round",
                    "summary": "Infinity raised funding with researchers from OpenAI and Anthropic; a Sequoia Capital observer commented on the market.",
                    "type": "融资",
                    "sector": "AI / AGI",
                    "publishedAt": "2026-07-20",
                    "institutions": ["Touring Capital"],
                    "source": {"url": "https://example.com/infinity-funding"},
                },
                {
                    "id": "openai-product",
                    "company": "OpenAI",
                    "companySlug": "openai",
                    "title": "OpenAI更新ChatGPT企业产品",
                    "summary": "ChatGPT面向企业客户提供模型推理、协作和API集成能力。",
                    "type": "产品发布",
                    "sector": "AI / AGI",
                    "publishedAt": "2026-06-01",
                    "source": {"url": "https://example.com/chatgpt-enterprise"},
                },
            ]
        }

    def test_enriches_every_company_and_institution_with_shared_schema(self) -> None:
        result = enrich_snapshot(copy.deepcopy(self.snapshot), self.articles, CATALOG)

        company = result["companies"]["openai"]
        self.assertEqual(result["schemaVersion"], 2)
        self.assertEqual(result["researchModelVersion"], 3)
        self.assertEqual(
            company["projectBackground"]["summary"],
            "研发并商业化通用人工智能模型与开发者平台。",
        )
        self.assertEqual(
            {item["name"] for item in company["technologyProducts"]},
            {"GPT 模型", "ChatGPT", "API"},
        )
        self.assertEqual(company["capitalSummary"]["eventCount"], 1)
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
        self.assertNotIn("Anthropic", company["researchTechnology"])
        self.assertEqual(company["researchModelVersion"], 3)
        self.assertEqual(company["capitalSummary"]["majorInvestors"], ["Sequoia Capital"])
        self.assertEqual(company["exitPerformance"]["status"], "暂无公开退出信息")

        institution = result["institutions"]["sequoia"]
        self.assertEqual(institution["recentYearSummary"]["investmentCount"], 1)
        self.assertEqual(institution["recentYearSummary"]["companies"], ["OpenAI"])
        self.assertEqual(institution["portfolio"][0]["name"], "OpenAI")
        self.assertIn("OpenAI", institution["classicCases"][0]["analysis"])

        checks = result["qualityGate"]["checks"]
        self.assertTrue(checks["companyResearchEnrichment"]["passed"])
        self.assertTrue(checks["institutionResearchEnrichment"]["passed"])
        self.assertTrue(result["qualityGate"]["passed"])

    def test_enrichment_is_idempotent(self) -> None:
        first = enrich_snapshot(copy.deepcopy(self.snapshot), self.articles, CATALOG)
        second = enrich_snapshot(copy.deepcopy(first), self.articles, CATALOG)
        self.assertEqual(first, second)

    def test_does_not_fabricate_disclosed_amounts_or_exit_events(self) -> None:
        result = enrich_snapshot(copy.deepcopy(self.snapshot), self.articles, CATALOG)
        company = result["companies"]["openai"]
        self.assertEqual(company["capitalSummary"]["disclosedAmounts"], [])
        self.assertEqual(company["capitalMarkets"], [])
        self.assertEqual(company["exitPerformance"]["latestEvent"], "")


if __name__ == "__main__":
    unittest.main()
