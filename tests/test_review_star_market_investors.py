import json
import tempfile
import unittest
from pathlib import Path

from tools import review_star_market_investors as review


class StarMarketInvestorReviewGateTests(unittest.TestCase):
    def _snapshot(self, investors):
        normalized = []
        for index, item in enumerate(investors, start=1):
            row = dict(item)
            row.setdefault("id", f"star-investor-{index}")
            row.setdefault("normalizedName", row.get("name", ""))
            row.setdefault("institutional", True)
            row.setdefault("sourcePage", 1)
            row.setdefault("sourceSection", "发行前股本结构")
            row.setdefault("investorType", "股权投资机构")
            row.setdefault("contactStatus", "not-disclosed-in-prospectus")
            normalized.append(row)
        return {
            "schemaVersion": 1,
            "companyCount": 1,
            "investorCount": len(normalized),
            "companies": {
                "sample": {
                    "slug": "sample",
                    "name": "示例科技",
                    "ticker": "688001",
                    "prospectus": {"url": "https://static.cninfo.com.cn/sample.pdf"},
                    "institutionalInvestorCount": len(normalized),
                    "investors": normalized,
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
        self.assertEqual(investor["reviewKey"], "sample:star-investor-1")
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

    def test_manifest_verification_can_publish_contact_and_metadata(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                    "preIpoShares": 1_000_000,
                    "preIpoOwnershipPct": 1.0,
                    "publicContact": {"phone": "010-12345678"},
                    "contactStatus": "prospectus-public",
                }
            ]
        )
        manifest = {
            "sample:star-investor-1": {
                "status": "verified",
                "reviewer": "research-editor",
                "reviewedAt": "2026-08-04T08:00:00+08:00",
                "note": "股东名称及同一行比例已核对。",
                "reasons": [],
            }
        }
        result = review.review_snapshot(snapshot, manifest)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "verified")
        self.assertEqual(investor["publicContact"]["phone"], "010-12345678")
        self.assertEqual(investor["reviewedBy"], "research-editor")
        self.assertEqual(investor["reviewSource"], "manifest")
        self.assertEqual(result["verifiedInvestorCount"], 1)
        self.assertEqual(result["reviewManifestDecisionCount"], 1)

    def test_stale_embedded_verification_is_not_trusted_without_manifest(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                    "reviewStatus": "verified",
                    "reviewedBy": "old-reviewer",
                    "reviewedAt": "2026-01-01",
                    "publicContact": {"phone": "010-12345678"},
                    "contactStatus": "prospectus-public",
                }
            ]
        )
        result = review.review_snapshot(snapshot, {})
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "needs_review")
        self.assertNotIn("reviewedBy", investor)
        self.assertNotIn("publicContact", investor)

    def test_manifest_verification_cannot_override_evidence_conflict(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "管理有限公司",
                    "evidence": "管理有限公司 1.00%",
                }
            ]
        )
        manifest = {
            "sample:star-investor-1": {
                "status": "verified",
                "reviewer": "research-editor",
                "reviewedAt": "2026-08-04",
                "note": "",
                "reasons": [],
            }
        }
        result = review.review_snapshot(snapshot, manifest)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "rejected")
        self.assertIn("review-manifest-evidence-conflict", investor["reviewReasons"])

    def test_manifest_can_record_a_human_rejection(self):
        snapshot = self._snapshot(
            [
                {
                    "name": "北京示例投资有限公司",
                    "evidence": "北京示例投资有限公司 100万股 1.00%",
                }
            ]
        )
        manifest = {
            "sample:star-investor-1": {
                "status": "rejected",
                "reviewer": "research-editor",
                "reviewedAt": "2026-08-04",
                "note": "该名称并非发行前直接股东。",
                "reasons": ["not-direct-shareholder"],
            }
        }
        result = review.review_snapshot(snapshot, manifest)
        investor = result["companies"]["sample"]["investors"][0]
        self.assertEqual(investor["reviewStatus"], "rejected")
        self.assertIn("human-rejected", investor["reviewReasons"])
        self.assertIn("not-direct-shareholder", investor["reviewReasons"])

    def test_unmatched_manifest_key_fails_instead_of_silently_disappearing(self):
        snapshot = self._snapshot(
            [{"name": "北京示例投资有限公司", "evidence": "北京示例投资有限公司 1.00%"}]
        )
        manifest = {
            "missing:star-investor-x": {
                "status": "rejected",
                "reviewer": "research-editor",
                "reviewedAt": "2026-08-04",
                "note": "",
                "reasons": [],
            }
        }
        with self.assertRaisesRegex(ValueError, "unmatched keys"):
            review.review_snapshot(snapshot, manifest)

    def test_manifest_loader_requires_auditable_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reviews.json"
            path.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "reviews": {
                            "sample:star-investor-1": {
                                "status": "verified",
                                "reviewer": "",
                                "reviewedAt": "not-a-date",
                            }
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                review.load_review_manifest(path)

    def test_reviewed_snapshot_validates_count_contact_and_review_rules(self):
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
