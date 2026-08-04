import unittest

from tools import review_star_market_investors as review


class StarMarketInvestorReviewGateTests(unittest.TestCase):
    def _snapshot(self, investors):
        return {
            "schemaVersion": 1,
            "companyCount": 1,
            "investorCount": len(investors),
            "companies": {
                "sample": {
                    "slug": "sample",
                    "name": "示例科技",
                    "ticker": "688001",
                    "prospectus": {"url": "https://static.cninfo.com.cn/sample.pdf"},
                    "institutionalInvestorCount": len(investors),
                    "investors": investors,
                }
            },
            "methodology": {},
        }

    def test_rebuilds_holding_from_same_evidence_line(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                    "preIpoShares": 99_000_000,
                    "preIpoOwnershipPct": 33.19,
                    "publicContact": {"phone": "010-12345678"},
                    "contactStatus": "prospectus-public",
                }
            ]
        )
        result = review.review_snapshot(snapshot)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["preIpoShares"], 1_000_000)
        self.assertEqual(investor["preIpoOwnershipPct"], 1.0)
        self.assertEqual(investor["reviewStatus"], "needs_review")
        self.assertNotIn("publicContact", investor)
        self.assertEqual(investor["contactStatus"], "withheld-pending-review")

    def test_ambiguous_same_line_values_are_rejected(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 5.00% 10.00%",
                    "preIpoOwnershipPct": 5.0,
                }
            ]
        )
        result = review.review_snapshot(snapshot)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "rejected")
        self.assertIn("ambiguous-holding-row", investor["reviewReasons"])
        self.assertNotIn("preIpoOwnershipPct", investor)

    def test_narrative_fragment_remains_in_audit_snapshot_but_is_rejected(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "事务合伙人为知己行远（天津）科技有限公司",
                    "evidence": "事务合伙人为知己行远（天津）科技有限公司，宋某担任执行事务合伙人。",
                }
            ]
        )
        result = review.review_snapshot(snapshot)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "rejected")
        self.assertIn("narrative-name-fragment", investor["reviewReasons"])
        self.assertEqual(result["investorCount"], 1)
        self.assertEqual(result["reviewCandidateCount"], 0)
        self.assertEqual(result["rejectedInvestorCount"], 1)

    def test_consistent_explicit_verification_can_publish_contact(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                    "preIpoShares": 1_000_000,
                    "preIpoOwnershipPct": 1.0,
                    "reviewStatus": "verified",
                    "reviewReasons": [],
                    "publicContact": {"phone": "010-12345678"},
                    "contactStatus": "prospectus-public",
                }
            ]
        )
        result = review.review_snapshot(snapshot)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "verified")
        self.assertEqual(investor["publicContact"]["phone"], "010-12345678")
        self.assertEqual(result["verifiedInvestorCount"], 1)

    def test_verified_evidence_conflict_is_downgraded_to_rejected(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "管理有限公司",
                    "evidence": "管理有限公司 1.00%",
                    "preIpoOwnershipPct": 1.0,
                    "reviewStatus": "verified",
                    "reviewReasons": [],
                }
            ]
        )
        result = review.review_snapshot(snapshot)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "rejected")
        self.assertIn("verified-evidence-conflict", investor["reviewReasons"])

    def test_reviewed_snapshot_validates_count_and_contact_rules(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                },
                {
                    "name": "管理有限公司",
                    "evidence": "管理有限公司",
                },
            ]
        )
        result = review.review_snapshot(snapshot)
        self.assertEqual(review.validate_reviewed_snapshot(result), [])
        self.assertEqual(
            result["investorCount"],
            result["reviewCandidateCount"] + result["rejectedInvestorCount"],
        )


if __name__ == "__main__":
    unittest.main()
