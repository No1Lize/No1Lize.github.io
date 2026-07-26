from __future__ import annotations

import copy
import unittest

from tools.refine_venture_research_evidence import refine_snapshot


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
{ slug:"agibot", name:"智元机器人", englishName:"AgiBot", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", headquarters:"上海", founded:"2023", summary:"研发具身智能机器人与软硬件平台。", product:"远征、灵犀、A2 旗舰版", source:official("智元机器人","https://example.com/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
{ slug:"sequoia-capital", name:"Sequoia Capital", englishName:"Sequoia Capital", region:"美国", type:"风险投资", stages:"全阶段", sectors:["AI","企业科技"], source:official("Sequoia Capital","https://capital.example.com/") },
];
export type IpoCompany = {};
'''


class VentureEvidenceAlignmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.snapshot = {
            "schemaVersion": 2,
            "researchModelVersion": 2,
            "generatedAt": "2026-07-25T12:00:00+00:00",
            "companies": {
                "agibot": {
                    "slug": "agibot",
                    "name": "智元机器人",
                    "status": "partial",
                    "background": "智元机器人启动港股上市，目标估值400亿港元。",
                    "projectBackground": {
                        "summary": "智元机器人启动港股上市，目标估值400亿港元。",
                        "problemSolved": "智元机器人启动港股上市。",
                        "marketOpportunity": "目标估值400亿港元。",
                    },
                    "technology": "远征A3采用全尺寸人形机器人架构。",
                    "products": ["远征", "灵犀", "A2 旗舰版"],
                    "technologyProducts": [
                        {
                            "name": "远征",
                            "category": "机器人 / 硬件",
                            "description": "远征A3采用全尺寸人形机器人架构。",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        },
                        {
                            "name": "灵犀",
                            "category": "机器人 / 硬件",
                            "description": "远征A3采用全尺寸人形机器人架构。",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        },
                        {
                            "name": "A2 旗舰版",
                            "category": "机器人 / 硬件",
                            "description": "远征A3采用全尺寸人形机器人架构。",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        },
                    ],
                    "team": [
                        {
                            "name": "邓泰华",
                            "role": "创始人",
                            "summary": "智元机器人参加产业大会。",
                            "background": "",
                            "previousExperience": "",
                            "sourceUrl": "https://example.com/team",
                        },
                        {
                            "name": "彭志辉",
                            "role": "联合创始人",
                            "summary": "彭志辉曾任华为工程师，后联合创办智元机器人。",
                            "background": "",
                            "previousExperience": "",
                            "sourceUrl": "https://example.com/team",
                        },
                    ],
                    "financing": [
                        {
                            "date": "2026-07-25",
                            "type": "产业投资",
                            "title": "智元机器人启动港股上市",
                            "summary": "公司计划进入港股公开市场。",
                            "sourceUrl": "https://example.com/ipo",
                        }
                    ],
                    "capitalMarkets": [],
                    "sources": [],
                    "qualityGate": {},
                }
            },
            "institutions": {
                "sequoia-capital": {
                    "slug": "sequoia-capital",
                    "name": "Sequoia Capital",
                    "status": "partial",
                    "overview": "Venture capital firm.",
                    "strategy": "Invests in technology.",
                    "team": [],
                    "recentInvestments": [],
                    "portfolio": [],
                    "classicCases": [],
                    "sources": [],
                }
            },
            "qualityGate": {"passed": True, "checks": {}},
        }
        self.articles = {
            "articles": [
                {
                    "company": "智元机器人",
                    "companySlug": "agibot",
                    "title": "智元机器人启动港股上市",
                    "summary": "公司计划进入港股公开市场。",
                    "type": "产业投资",
                    "publishedAt": "2026-07-25",
                    "source": {"url": "https://example.com/ipo"},
                },
                {
                    "company": "智元机器人",
                    "companySlug": "agibot",
                    "title": "智元机器人完成B轮融资",
                    "summary": "Sequoia Capital参与智元机器人B轮融资。",
                    "type": "融资",
                    "publishedAt": "2026-06-01",
                    "institutions": ["Sequoia Capital"],
                    "source": {"url": "https://example.com/funding"},
                },
                {
                    "company": "Infinity",
                    "companySlug": "infinity",
                    "title": "Infinity完成融资",
                    "summary": "Infinity完成融资，研究人员曾来自智元机器人，Sequoia Capital未参与本轮。",
                    "type": "融资",
                    "publishedAt": "2026-07-20",
                    "institutions": ["Touring Capital"],
                    "source": {"url": "https://example.com/infinity"},
                },
                {
                    "company": "智元机器人",
                    "companySlug": "agibot",
                    "title": "远征A3技术说明",
                    "summary": "远征A3采用全尺寸人形机器人架构和自主控制系统。",
                    "type": "产品发布",
                    "publishedAt": "2026-05-01",
                    "source": {"url": "https://example.com/a3"},
                },
                {
                    "company": "智元机器人",
                    "companySlug": "agibot",
                    "title": "彭志辉团队介绍",
                    "summary": "彭志辉曾任华为工程师，后联合创办智元机器人。",
                    "type": "公司动态",
                    "publishedAt": "2026-04-01",
                    "source": {"url": "https://example.com/team"},
                },
            ]
        }

    def test_aligns_background_products_team_and_capital_events(self) -> None:
        refined, diagnostics = refine_snapshot(
            copy.deepcopy(self.snapshot), self.articles, CATALOG
        )
        company = refined["companies"]["agibot"]

        self.assertEqual(
            company["projectBackground"]["summary"],
            "研发具身智能机器人与软硬件平台。",
        )
        self.assertNotIn("上市", company["projectBackground"]["summary"])

        products = {item["name"]: item for item in company["technologyProducts"]}
        self.assertIn("远征A3", products["远征"]["description"])
        self.assertNotIn("远征A3", products["灵犀"]["description"])
        self.assertIn("尚未识别", products["灵犀"]["description"])
        self.assertNotIn("远征A3", products["A2 旗舰版"]["description"])

        team = {item["name"]: item for item in company["team"]}
        self.assertEqual(team["邓泰华"]["summary"], "")
        self.assertIn("彭志辉", team["彭志辉"]["summary"])

        self.assertEqual(len(company["financing"]), 1)
        self.assertNotIn("Infinity", company["financing"][0]["title"])
        self.assertNotIn("Infinity", company["projectBackground"]["summary"])
        self.assertIn("B轮融资", company["financing"][0]["title"])
        self.assertEqual(len(company["capitalMarkets"]), 1)
        self.assertEqual(company["capitalMarkets"][0]["type"], "上市")
        self.assertIn("港股上市", company["capitalMarkets"][0]["title"])
        self.assertGreater(diagnostics["companiesRefined"], 0)

    def test_builds_recent_investment_only_from_explicit_investment_evidence(self) -> None:
        refined, _ = refine_snapshot(
            copy.deepcopy(self.snapshot), self.articles, CATALOG
        )
        institution = refined["institutions"]["sequoia-capital"]
        self.assertEqual(len(institution["recentInvestments"]), 1)
        self.assertEqual(institution["recentInvestments"][0]["name"], "智元机器人")
        self.assertEqual(
            institution["recentInvestments"][0]["sourceUrl"],
            "https://example.com/funding",
        )

    def test_is_idempotent(self) -> None:
        first, _ = refine_snapshot(copy.deepcopy(self.snapshot), self.articles, CATALOG)
        second, _ = refine_snapshot(copy.deepcopy(first), self.articles, CATALOG)
        self.assertEqual(first, second)

    def test_project_background_does_not_feed_mutable_background_back(self) -> None:
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["companies"]["agibot"]["background"] = (
            "智元机器人是一家具身智能机器人公司。"
            "智元机器人面向制造业客户提供具身智能机器人解决方案并推动规模化部署。"
        )

        first, _ = refine_snapshot(snapshot, self.articles, CATALOG)
        second, _ = refine_snapshot(copy.deepcopy(first), self.articles, CATALOG)

        self.assertEqual(first, second)
        self.assertEqual(
            first["companies"]["agibot"]["projectBackground"]["problemSolved"],
            "",
        )
        self.assertEqual(
            first["companies"]["agibot"]["projectBackground"]["marketOpportunity"],
            "",
        )


if __name__ == "__main__":
    unittest.main()
