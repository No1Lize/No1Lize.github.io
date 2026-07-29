import json
import tempfile
import unittest
from pathlib import Path

from tools import crawl_star_market_investors as star


class StarMarketInvestorTests(unittest.TestCase):
    def _write_json(self, path: Path, payload: object) -> None:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def test_load_star_listings_only_accepts_enabled_688_a_share(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tracking = root / "tracking.json"
            config = root / "config.json"
            self._write_json(
                tracking,
                {
                    "listedCompanies": [
                        {
                            "catalogSlug": "cambricon",
                            "name": "寒武纪",
                            "ticker": "688256",
                            "market": "A股",
                            "sector": "半导体",
                            "enabled": True,
                        },
                        {
                            "catalogSlug": "bgi",
                            "name": "华大基因",
                            "ticker": "300676",
                            "market": "A股",
                            "sector": "生物科技",
                            "enabled": True,
                        },
                        {
                            "catalogSlug": "disabled",
                            "name": "停用公司",
                            "ticker": "688999",
                            "market": "A股",
                            "sector": "半导体",
                            "enabled": False,
                        },
                    ]
                },
            )
            self._write_json(config, {"schemaVersion": 1, "settings": {}, "extraListings": []})
            listings = star.load_star_listings(tracking, config)
            self.assertEqual([item.ticker for item in listings], ["688256"])

    def test_final_prospectus_beats_summary_and_application_drafts(self):
        final = star.prospectus_title_score("首次公开发行股票并在科创板上市招股说明书")
        summary = star.prospectus_title_score("首次公开发行股票招股说明书摘要")
        draft = star.prospectus_title_score("首次公开发行股票招股说明书（申报稿）")
        unrelated = star.prospectus_title_score("2025年年度报告")
        self.assertGreater(final, summary)
        self.assertGreater(final, draft)
        self.assertLess(unrelated, 0)

    def test_extracts_institutional_shareholder_and_excludes_natural_person(self):
        pages = [
            star.PdfPage(
                88,
                """
                发行前股本结构
                序号 股东名称 持股数量 持股比例
                1 北京示例创业投资基金（有限合伙） 1,250万股 12.50%
                2 张三 800万股 8.00%
                北京示例创业投资基金（有限合伙）住所：北京市海淀区科创路1号
                联系电话：010-12345678 电子邮箱：contact@examplefund.cn
                """,
            )
        ]
        investors = star.extract_institutional_investors(
            pages,
            "示例科技",
            max_investors=20,
        )
        self.assertEqual(len(investors), 1)
        investor = investors[0]
        self.assertEqual(investor["name"], "北京示例创业投资基金（有限合伙）")
        self.assertEqual(investor["preIpoShares"], 12500000)
        self.assertEqual(investor["preIpoOwnershipPct"], 12.5)
        self.assertEqual(investor["publicContact"]["phone"], "010-12345678")
        self.assertEqual(investor["publicContact"]["email"], "contact@examplefund.cn")
        self.assertNotIn("张三", json.dumps(investors, ensure_ascii=False))

    def test_duplicate_institution_evidence_prefers_row_with_holding_percentage(self):
        pages = [
            star.PdfPage(
                30,
                "主要股东情况 北京示例资本有限公司为发行人机构股东。",
            ),
            star.PdfPage(
                31,
                "发行前股本结构 北京示例资本有限公司 500万股 5.25%",
            ),
        ]
        investors = star.extract_institutional_investors(
            pages,
            "示例科技",
            max_investors=20,
        )
        self.assertEqual(len(investors), 1)
        self.assertEqual(investors[0]["preIpoOwnershipPct"], 5.25)

    def test_contact_and_evidence_redact_mobile_and_identity_numbers(self):
        pages = [
            star.PdfPage(
                42,
                """
                发行人股东情况
                上海示例股权投资有限公司 300万股 3.00%
                上海示例股权投资有限公司办公地址：上海市浦东新区示例路8号
                联系人李某，手机13812345678，身份证310101199001011234，电话021-87654321。
                """,
            )
        ]
        investors = star.extract_institutional_investors(
            pages,
            "示例科技",
            max_investors=20,
        )
        serialized = json.dumps(investors, ensure_ascii=False)
        self.assertNotIn("13812345678", serialized)
        self.assertNotIn("310101199001011234", serialized)
        self.assertIn("021-87654321", serialized)

    def test_snapshot_validation_rejects_personal_mobile_in_contact_fields(self):
        snapshot = {
            "schemaVersion": 1,
            "companyCount": 1,
            "investorCount": 1,
            "companies": {
                "sample": {
                    "ticker": "688001",
                    "prospectus": {"url": "https://static.cninfo.com.cn/sample.pdf"},
                    "investors": [
                        {
                            "name": "示例投资有限公司",
                            "normalizedName": "示例投资有限公司",
                            "institutional": True,
                            "sourcePage": 1,
                            "publicContact": {"phone": "13812345678"},
                        }
                    ],
                }
            },
        }
        errors = star.validate_snapshot(snapshot, require_companies=True)
        self.assertTrue(any("mobile number" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
