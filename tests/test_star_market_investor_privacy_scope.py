import unittest

from tools import crawl_star_market_investors as star


class StarInvestorPrivacyScopeTests(unittest.TestCase):
    def _snapshot(self, *, evidence: str, sha256: str) -> dict:
        return {
            "schemaVersion": 1,
            "companyCount": 1,
            "investorCount": 1,
            "companies": {
                "sample": {
                    "name": "示例科技",
                    "ticker": "688001",
                    "sector": "半导体",
                    "prospectus": {
                        "title": "示例科技首次公开发行股票招股说明书",
                        "url": "https://static.cninfo.com.cn/sample.pdf",
                        "sha256": sha256,
                        "announcementId": "12345678901234567890",
                    },
                    "issuerInvestorRelations": {},
                    "investors": [
                        {
                            "id": "star-investor-13812345678",
                            "name": "示例创业投资有限公司",
                            "normalizedName": "示例创业投资有限公司",
                            "institutional": True,
                            "sourcePage": 88,
                            "evidence": evidence,
                            "contactStatus": "not-disclosed-in-prospectus",
                        }
                    ],
                }
            },
        }

    def test_machine_ids_and_hashes_do_not_trigger_personal_phone_detection(self):
        snapshot = self._snapshot(
            evidence="示例创业投资有限公司为发行前机构股东。",
            sha256="13812345678" + "a" * 53,
        )
        errors = star.validate_snapshot(snapshot, require_companies=True)
        self.assertFalse(any("mobile number" in error for error in errors), errors)

    def test_human_readable_evidence_still_rejects_personal_mobile(self):
        snapshot = self._snapshot(
            evidence="联系人手机13812345678",
            sha256="a" * 64,
        )
        errors = star.validate_snapshot(snapshot, require_companies=True)
        self.assertTrue(any("mobile number" in error for error in errors), errors)

    def test_public_contact_still_rejects_identity_number(self):
        snapshot = self._snapshot(
            evidence="示例创业投资有限公司为发行前机构股东。",
            sha256="a" * 64,
        )
        snapshot["companies"]["sample"]["investors"][0]["publicContact"] = {
            "officeAddress": "证件号310101199001011234",
            "sourcePage": 90,
            "scope": "招股说明书公开的机构级联系方式",
        }
        errors = star.validate_snapshot(snapshot, require_companies=True)
        self.assertTrue(any("identity number" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
