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

    def test_payload_normalization_updates_all_entity_types_and_quality_gate(self) -> None:
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "agibot": {
                    "slug": "agibot",
                    "name": "智元机器人",
                    "status": "partial",
                    "background": "研发具身智能机器人。",
                    "technology": "构建机器人软硬件平台。",
                    "products": ["灵犀等机器人系列。", "具身智能服务机器人大赛"],
                    "team": [
                        {"name": "智元", "role": "合伙人", "summary": "", "sourceUrl": "https://example.com/team"},
                        {"name": "邓泰华", "role": "创始人", "summary": "", "sourceUrl": "https://example.com/team"},
                    ],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [],
                }
            },
            "institutions": {
                "sample-capital": {
                    "slug": "sample-capital",
                    "name": "样本资本",
                    "status": "partial",
                    "overview": "样本投资机构。",
                    "strategy": "投资机器人项目。",
                    "team": [
                        {"name": "样本资本", "role": "合伙人", "summary": "", "sourceUrl": "https://capital.example.com/team"},
                        {"name": "张三", "role": "合伙人", "summary": "", "sourceUrl": "https://capital.example.com/team"},
                    ],
                    "recentInvestments": [],
                    "portfolio": [],
                    "classicCases": [],
                    "sources": [],
                }
            },
            "sourceStatus": [
                {"kind": "company", "slug": "agibot"},
                {"kind": "institution", "slug": "sample-capital"},
            ],
            "qualityGate": {
                "checks": {
                    "companyResearchEnrichment": {
                        "actual": 1,
                        "required": 1,
                        "passed": True,
                    },
                    "institutionResearchEnrichment": {
                        "actual": 1,
                        "required": 1,
                        "passed": True,
                    },
                },
                "passed": True,
            },
        }
        normalized, stats = normalizer.normalize_payload(payload, CATALOG)
        self.assertEqual(normalized["companies"]["agibot"]["products"], ["灵犀"])
        self.assertEqual(
            [item["name"] for item in normalized["companies"]["agibot"]["team"]],
            ["邓泰华"],
        )
        self.assertEqual(
            [item["name"] for item in normalized["institutions"]["sample-capital"]["team"]],
            ["张三"],
        )
        self.assertEqual(stats["companyProducts"], 1)
        checks = normalized["qualityGate"]["checks"]
        self.assertTrue(checks["profileConsistency"]["passed"])
        self.assertTrue(checks["companyResearchEnrichment"]["passed"])
        self.assertTrue(checks["institutionResearchEnrichment"]["passed"])
        self.assertTrue(normalized["qualityGate"]["passed"])


if __name__ == "__main__":
    unittest.main()
