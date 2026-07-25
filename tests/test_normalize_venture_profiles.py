from __future__ import annotations

import unittest

from tools import normalize_venture_profiles as normalizer


CATALOG = '''
export const companies: Company[] = [
  { slug:"agibot", name:"智元机器人", englishName:"AgiBot", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", founded:"2023", headquarters:"上海", summary:"研发具身智能机器人。", product:"远征、灵犀等机器人系列。", source:official("智元机器人","https://example.com/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"sample-capital", name:"样本资本", englishName:"Sample Capital", region:"中国", type:"风险投资", stages:"早期", sectors:["机器人"], source:official("样本资本","https://capital.example.com/") },
];
export type IpoCompany = {};
'''


class VentureProfileConsistencyTests(unittest.TestCase):
    def test_product_suffixes_events_and_document_labels_are_removed(self) -> None:
        self.assertEqual(
            normalizer.normalize_product_items(
                [
                    "远征",
                    "灵犀等机器人系列。",
                    "产品手册",
                    "具身智能服务机器人大赛",
                    "Genie Studio具身智能开发平台",
                ]
            ),
            ["远征", "灵犀", "Genie Studio具身智能开发平台"],
        )

    def test_brand_and_role_fragments_are_removed_from_team(self) -> None:
        team = normalizer.normalize_team_members(
            [
                {"name": "智元", "role": "合伙人", "summary": "", "sourceUrl": "https://example.com/team"},
                {"name": "高级副", "role": "总裁", "summary": "", "sourceUrl": "https://example.com/team"},
                {"name": "具身业务部", "role": "总裁", "summary": "", "sourceUrl": "https://example.com/team"},
                {"name": "邓泰华", "role": "创始人", "summary": "", "sourceUrl": "https://example.com/team"},
            ],
            ("智元机器人", "AgiBot"),
        )
        self.assertEqual([item["name"] for item in team], ["邓泰华"])

    def test_false_policy_and_homepage_events_are_removed(self) -> None:
        financing = normalizer.normalize_capital_events(
            [
                {
                    "type": "融资",
                    "title": "Announcing our updated Responsible Scaling Policy",
                    "summary": "The company published updated safety safeguards.",
                    "sourceUrl": "https://example.com/policy",
                },
                {
                    "date": "2026-07-01",
                    "type": "融资",
                    "title": "公司完成B轮融资",
                    "summary": "本轮由样本资本领投。",
                    "round": "B轮",
                    "investors": ["样本资本"],
                    "sourceUrl": "https://example.com/funding",
                },
            ],
            capital_market=False,
        )
        self.assertEqual([item["title"] for item in financing], ["公司完成B轮融资"])

        capital_markets = normalizer.normalize_capital_events(
            [
                {
                    "type": "资本市场",
                    "title": "Transforming industry with advanced technology",
                    "summary": "The company builds autonomous systems.",
                    "sourceUrl": "https://example.com/",
                },
                {
                    "date": "2026-06-01",
                    "type": "上市",
                    "title": "公司在交易所上市",
                    "summary": "公司完成首次公开发行。",
                    "sourceUrl": "https://example.com/ipo",
                },
            ],
            capital_market=True,
        )
        self.assertEqual([item["title"] for item in capital_markets], ["公司在交易所上市"])

    def test_structured_product_cards_follow_cleaned_products(self) -> None:
        cards = normalizer.normalize_technology_products(
            [
                {
                    "name": "灵犀等机器人系列。",
                    "category": "机器人 / 硬件",
                    "description": "旧名称卡片。",
                },
                {
                    "name": "具身智能服务机器人大赛",
                    "category": "活动",
                    "description": "不应保留。",
                },
            ],
            ["灵犀"],
        )
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["name"], "灵犀")
        self.assertNotIn("大赛", cards[0]["name"])

    def test_payload_normalization_updates_all_entity_types_and_quality_gate(self) -> None:
        payload = {
            "schemaVersion": 2,
            "researchModelVersion": 2,
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "agibot": {
                    "slug": "agibot",
                    "name": "智元机器人",
                    "status": "partial",
                    "researchModelVersion": 2,
                    "background": "研发具身智能机器人。",
                    "projectBackground": {"summary": "研发具身智能机器人。"},
                    "technology": "构建机器人软硬件平台。",
                    "products": ["灵犀等机器人系列。", "具身智能服务机器人大赛"],
                    "technologyProducts": [
                        {"name": "灵犀等机器人系列。", "description": "机器人产品。"},
                        {"name": "具身智能服务机器人大赛", "description": "活动。"},
                    ],
                    "team": [
                        {"name": "智元", "role": "合伙人", "summary": "", "sourceUrl": "https://example.com/team"},
                        {"name": "邓泰华", "role": "创始人", "summary": "", "sourceUrl": "https://example.com/team"},
                    ],
                    "financing": [
                        {
                            "type": "融资",
                            "title": "安全政策更新",
                            "summary": "公司更新安全政策。",
                            "sourceUrl": "https://example.com/policy",
                        }
                    ],
                    "capitalSummary": {},
                    "capitalMarkets": [],
                    "exitPerformance": {},
                    "sources": [],
                }
            },
            "institutions": {
                "sample-capital": {
                    "slug": "sample-capital",
                    "name": "样本资本",
                    "status": "partial",
                    "researchModelVersion": 2,
                    "overview": "样本投资机构。",
                    "strategy": "投资机器人项目。",
                    "team": [
                        {"name": "样本资本", "role": "合伙人", "summary": "", "sourceUrl": "https://capital.example.com/team"},
                        {"name": "张三", "role": "合伙人", "summary": "", "sourceUrl": "https://capital.example.com/team"},
                    ],
                    "recentInvestments": [],
                    "recentYearSummary": {
                        "periodStart": "2025-07-25",
                        "periodEnd": "2026-07-25",
                        "investmentCount": 0,
                        "companies": [],
                        "sectors": [],
                        "rounds": [],
                        "summary": "暂无记录。",
                    },
                    "portfolio": [],
                    "classicCases": [],
                    "sources": [],
                }
            },
            "sourceStatus": [
                {"kind": "company", "slug": "agibot"},
                {"kind": "institution", "slug": "sample-capital"},
            ],
            "qualityGate": {"checks": {}, "passed": True},
        }
        normalized, stats = normalizer.normalize_payload(payload, CATALOG)
        company = normalized["companies"]["agibot"]
        self.assertEqual(company["products"], ["灵犀"])
        self.assertEqual([item["name"] for item in company["technologyProducts"]], ["灵犀"])
        self.assertEqual(company["financing"], [])
        self.assertEqual(company["capitalSummary"]["eventCount"], 0)
        self.assertEqual(
            [item["name"] for item in company["team"]],
            ["邓泰华"],
        )
        self.assertEqual(
            [item["name"] for item in normalized["institutions"]["sample-capital"]["team"]],
            ["张三"],
        )
        self.assertEqual(stats["companyProducts"], 1)
        self.assertEqual(stats["companyFinancing"], 1)
        checks = normalized["qualityGate"]["checks"]
        self.assertTrue(checks["profileConsistency"]["passed"])
        self.assertTrue(checks["companyResearchEnrichment"]["passed"])
        self.assertTrue(checks["institutionResearchEnrichment"]["passed"])
        self.assertTrue(normalized["qualityGate"]["passed"])


if __name__ == "__main__":
    unittest.main()
