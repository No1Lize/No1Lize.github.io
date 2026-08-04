import unittest

from tools.review_star_market_investors import review_snapshot
from tools.star_investor_quality import extract_same_line_holding


class StrictTableHoldingCompatibilityTests(unittest.TestCase):
    def test_primary_table_row_without_percent_symbols_is_bound(self):
        shares, pct, reasons = extract_same_line_holding(
            "5 国投基金 14,124,730 3.92 14,124,730 3.53",
            "国投（上海）科技成果转化创业投资基金企业（有限合伙）",
        )
        self.assertEqual(shares, 14124730)
        self.assertEqual(pct, 3.92)
        self.assertEqual(reasons, [])

    def test_resolved_legal_name_can_use_strict_alias_row_evidence(self):
        snapshot = {
            "companies": {
                "cambricon": {
                    "name": "中科寒武纪科技股份有限公司",
                    "investors": [
                        {
                            "id": "star-investor-sample",
                            "name": "国投（上海）科技成果转化创业投资基金企业（有限合伙）",
                            "disclosedName": "国投基金",
                            "normalizedName": "国投上海科技成果转化创业投资基金企业有限合伙",
                            "institutional": True,
                            "investorType": "股权投资机构",
                            "sourcePage": 93,
                            "sourceSection": "公司本次发行前后股本情况",
                            "evidence": "5 国投基金 14,124,730 3.92 14,124,730 3.53",
                            "nameResolution": "definitions",
                            "preIpoShares": 14124730,
                            "preIpoOwnershipPct": 3.92,
                        }
                    ],
                }
            }
        }
        reviewed = review_snapshot(snapshot, {})
        investor = reviewed["companies"]["cambricon"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "needs_review")
        self.assertEqual(investor["preIpoShares"], 14124730)
        self.assertEqual(investor["preIpoOwnershipPct"], 3.92)

    def test_related_party_sentence_is_not_fabricated_as_holding_row(self):
        shares, pct, reasons = extract_same_line_holding(
            "湖北长江招银产业基金管理有限公司 董事长 关联方",
            "湖北长江招银产业基金管理有限公司",
        )
        self.assertIsNone(shares)
        self.assertIsNone(pct)
        self.assertEqual(reasons, [])


if __name__ == "__main__":
    unittest.main()
