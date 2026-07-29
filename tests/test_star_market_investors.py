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

    def test_crawler_wrapper_uses_structured_pre_and_post_ipo_table(self):
        pages = [
            star.PdfPage(21, "示例基金 指 北京示例创业投资基金（有限合伙）"),
            star.PdfPage(
                88,
                """
                公司本次发行前后公司股本情况
                序号 股东名称/姓名 本次发行前 本次发行后
                持股数（股） 占比（%） 持股数（股） 占比（%）
                1 张三 80,000,000 80.00 80,000,000 72.00
                2 示例基金 12,500,000 12.50 12,500,000 11.25
                """,
            ),
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
        self.assertNotIn("张三", json.dumps(investors, ensure_ascii=False))

    def test_snapshot_validation_rejects_personal_mobile_in_contact_fields(self):
        snapshot = {
            "schemaVersion": 1,
            "companyCount": 1,
            "investorCount": 1,
            "companies": {
                "sample": {
                    "ticker": "688001",
                    "prospectus": {
                        "title": "示例科技首次公开发行股票招股说明书",
                        "url": "https://static.cninfo.com.cn/sample.pdf",
                    },
                    "investors": [
                        {
                            "name": "示例投资有限公司",
                            "normalizedName": "示例投资有限公司",
                            "institutional": True,
                            "sourcePage": 1,
                            "sourceSection": "公司本次发行前后股本情况",
                            "evidence": "2 示例投资有限公司 1,000,000 10.00 1,000,000 9.00",
                            "preIpoShares": 1000000,
                            "preIpoOwnershipPct": 10,
                            "nameResolution": "definitions",
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
