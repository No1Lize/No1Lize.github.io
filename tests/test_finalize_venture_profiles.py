from __future__ import annotations

import copy
import unittest
from datetime import UTC, datetime

from tools import finalize_venture_profiles as finalizer


class VentureProfileFinalizerTests(unittest.TestCase):
    def test_products_remove_pure_research_but_keep_api(self) -> None:
        products = finalizer.finalize_products(
            ["Claude Platform", "Terms of Service: US K-12"],
            "Claude 模型、企业 API 与安全研究。",
        )
        self.assertEqual(products[:2], ["Claude 模型", "企业 API"])
        self.assertIn("Claude Platform", products)
        self.assertNotIn("安全研究。", products)

    def test_team_preserves_structured_experience(self) -> None:
        team = finalizer.finalize_team(
            [
                {
                    "name": "邓泰华",
                    "role": "创始人",
                    "summary": "创始团队成员。",
                    "background": "曾负责企业技术战略。",
                    "previousExperience": "曾任大型科技公司高管。",
                    "sourceUrl": "https://example.com/team",
                },
                {
                    "name": "关于智元",
                    "role": "合伙人",
                    "sourceUrl": "https://example.com/team",
                },
            ],
            ("智元机器人", "AgiBot"),
        )
        self.assertEqual([item["name"] for item in team], ["邓泰华"])
        self.assertEqual(team[0]["background"], "曾负责企业技术战略。")
        self.assertEqual(team[0]["previousExperience"], "曾任大型科技公司高管。")

    def test_financing_rejects_round_like_product_copy(self) -> None:
        rows = finalizer.finalize_financing(
            [
                {
                    "date": "2026-01-01",
                    "type": "融资",
                    "title": "Series C autonomous platform",
                    "summary": "The Series C platform is designed for industrial deployment.",
                    "round": "Series C",
                    "sourceUrl": "https://example.com/product",
                },
                {
                    "date": "2026-01-02",
                    "type": "融资",
                    "title": "Company raises Series C",
                    "summary": "The company raised $500 million in a Series C funding round.",
                    "round": "Series C",
                    "amount": "$500 million",
                    "sourceUrl": "https://example.com/funding",
                },
            ]
        )
        self.assertEqual(len(rows), 1)
        self.assertIn("raises", rows[0]["title"])

    def test_recent_investments_use_actual_one_year_window(self) -> None:
        rows = finalizer.finalize_recent_investments(
            [
                {
                    "name": "OldCo",
                    "date": "2024-12-01",
                    "summary": "A disclosed investment in an older financing round.",
                    "sourceUrl": "https://example.com/old",
                },
                {
                    "name": "CurrentCo",
                    "date": "2026-03-01",
                    "summary": "A disclosed investment in the current reporting window.",
                    "sourceUrl": "https://example.com/current",
                },
                {
                    "name": "FutureCo",
                    "date": "2026-08-01",
                    "summary": "A future-dated record that should not be accepted.",
                    "sourceUrl": "https://example.com/future",
                },
            ],
            datetime(2026, 7, 25, tzinfo=UTC),
        )
        self.assertEqual([item["name"] for item in rows], ["CurrentCo"])

    def test_classic_cases_preserve_analysis_fields_and_require_evidence(self) -> None:
        values = [
            {
                "name": "GenericCo",
                "companySlug": "generic",
                "investmentLogic": "公开组合记录。",
                "followOnPerformance": "后续资料待补充。",
                "exitPerformance": "退出资料待补充。",
                "analysis": "公开资料将 GenericCo 列入投资组合，其他事实仍待公开资料补充。" * 2,
                "sourceUrl": "https://example.com/generic",
            },
            {
                "name": "ListedCo",
                "companySlug": "listed",
                "investmentLogic": "机构在成长期布局该项目。",
                "followOnPerformance": "公司完成后续融资并扩大商业化部署。",
                "exitPerformance": "公司随后上市。",
                "analysis": "机构在成长期布局该项目，公司完成后续融资并扩大商业化部署，随后实现上市退出。",
                "sourceUrl": "https://example.com/listed",
            },
        ]
        rows = finalizer.finalize_classic_cases(values, {"listed": {}}, {"listed"})
        self.assertEqual([item["name"] for item in rows], ["ListedCo"])
        self.assertEqual(rows[0]["investmentLogic"], "机构在成长期布局该项目。")
        self.assertEqual(rows[0]["exitPerformance"], "公司随后上市。")

    def test_snapshot_finalization_is_idempotent(self) -> None:
        catalog = '''
export const companies: Company[] = [
  { slug:"example", name:"Example", region:"美国", sector:"AI", stage:"成长期", status:"运营中", summary:"Example summary.", product:"Example API、安全研究。", source:official("Example","https://example.com/"), confidence:0.9 },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [
  { slug:"fund", name:"Fund", region:"美国", type:"VC", stages:"Early", sectors:["AI"], source:official("Fund","https://fund.example.com/") },
];
export type IpoCompany = {};
'''
        payload = {
            "schemaVersion": 2,
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "example": {
                    "slug": "example",
                    "name": "Example",
                    "background": "Example builds reliable AI systems.",
                    "technology": "Example API supports enterprise deployment.",
                    "products": ["Example API", "安全研究。"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "sources": [{"name": "Example", "url": "https://example.com/", "level": "官方披露"}],
                }
            },
            "institutions": {
                "fund": {
                    "slug": "fund",
                    "name": "Fund",
                    "overview": "Fund is an early-stage investment firm.",
                    "strategy": "Fund invests in AI companies.",
                    "team": [],
                    "recentInvestments": [],
                    "portfolio": [],
                    "classicCases": [],
                    "sources": [{"name": "Fund", "url": "https://fund.example.com/", "level": "官方披露"}],
                }
            },
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = finalizer.finalize_snapshot(copy.deepcopy(payload), catalog)
        second, _ = finalizer.finalize_snapshot(copy.deepcopy(cleaned), catalog)
        self.assertEqual(second, cleaned)
        self.assertNotIn("安全研究。", cleaned["companies"]["example"]["products"])
        self.assertTrue(cleaned["qualityGate"]["checks"]["finalSemanticConsistency"]["passed"])


if __name__ == "__main__":
    unittest.main()
