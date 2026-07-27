from __future__ import annotations

import copy
import unittest

from tools import refine_venture_research_evidence as refiner


CATALOG = '''
export type Company = {};
export const companies: Company[] = [
{ slug:"agibot", name:"智元机器人", englishName:"AgiBot", region:"中国", sector:"机器人", stage:"成长期", status:"运营中", headquarters:"上海", founded:"2023", summary:"研发具身智能机器人与软硬件平台。", product:"远征、灵犀", source:official("智元机器人","https://example.com/") },
];
export type Institution = {};
export const institutionCatalog: Institution[] = [];
export type IpoCompany = {};
'''


class VentureProjectEvidenceStabilityTests(unittest.TestCase):
    def test_existing_entity_bound_market_sentence_is_stable(self) -> None:
        snapshot = {
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "agibot": {
                    "slug": "agibot",
                    "name": "智元机器人",
                    "background": "智元机器人研发具身智能机器人与软硬件平台。",
                    "technology": "智元机器人面向行业应用部署具身智能系统。",
                    "products": ["远征", "灵犀"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "projectBackground": {
                        "summary": "智元机器人研发具身智能机器人与软硬件平台。",
                        "problemSolved": "",
                        "marketOpportunity": "智元机器人面向行业客户部署具身智能系统。",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        articles = {
            "articles": [
                {
                    "title": "智元机器人产业应用更新",
                    "summary": "智元机器人在多个行业市场推进商业化部署。",
                    "companies": ["智元机器人"],
                    "publishedAt": "2026-07-20",
                    "source": {"url": "https://example.com/news"},
                }
            ]
        }
        first, _ = refiner.refine_snapshot(copy.deepcopy(snapshot), articles, CATALOG)
        second, diagnostics = refiner.refine_snapshot(copy.deepcopy(first), articles, CATALOG)
        self.assertEqual(first, second)
        self.assertEqual(diagnostics["companiesRefined"], 0)
        self.assertEqual(
            first["companies"]["agibot"]["projectBackground"]["marketOpportunity"],
            "智元机器人面向行业客户部署具身智能系统。",
        )

    def test_unrelated_problem_sentence_is_rejected(self) -> None:
        snapshot = {
            "generatedAt": "2026-07-25T00:00:00+00:00",
            "companies": {
                "agibot": {
                    "slug": "agibot",
                    "name": "智元机器人",
                    "background": "智元机器人研发具身智能机器人。",
                    "technology": "智元机器人开发具身智能系统。",
                    "products": ["远征"],
                    "technologyProducts": [],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "projectBackground": {
                        "summary": "智元机器人研发具身智能机器人。",
                        "problemSolved": "另一家公司帮助客户降低成本。",
                        "marketOpportunity": "",
                    },
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, _ = refiner.refine_snapshot(copy.deepcopy(snapshot), {"articles": []}, CATALOG)
        self.assertEqual(
            cleaned["companies"]["agibot"]["projectBackground"]["problemSolved"],
            "",
        )


if __name__ == "__main__":
    unittest.main()
