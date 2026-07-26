from __future__ import annotations

import hashlib
import unittest

from tools import enrich_professional_venture_sources as professional
from tools.venture_profile_extraction import CatalogCompany


class ProfessionalVentureSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.company = CatalogCompany(
            slug="agibot",
            name="智元机器人",
            english_name="AgiBot",
            region="中国",
            sector="机器人",
            stage="成长期",
            status="运营中",
            summary="研发具身智能机器人。",
            product="人形机器人。",
            source_name="智元机器人",
            source_url="https://www.zhiyuan-robot.com/",
        )

    def test_qcc_auth_header_matches_documented_signature(self) -> None:
        headers = professional._qcc_headers("app-key", "secret-key", timestamp=1712345678)
        expected = hashlib.md5(
            b"app-key1712345678secret-key"
        ).hexdigest().upper()
        self.assertEqual(headers, {"Token": expected, "Timespan": "1712345678"})

    def test_qcc_company_parser_extracts_shareholders_and_equity_changes(self) -> None:
        payload = {
            "Status": "200",
            "Result": {
                "Name": "智元创新（上海）科技股份有限公司",
                "CreditCode": "91310000TEST",
                "Status": "存续",
                "RegistCapi": "1000万元人民币",
                "RecCap": "600万元人民币",
                "OperName": "测试法人",
                "Partners": [
                    {
                        "StockName": "测试股东",
                        "StockPercent": "31.5%",
                        "ShouldCapi": "315万元人民币",
                        "RealCapi": "200万元人民币",
                        "FinalBenefitPercent": "31.5%",
                        "TagsList": ["最终受益人", "大股东"],
                    }
                ],
                "ChangeRecords": [
                    {
                        "ChangeDate": "2025-01-02",
                        "ProjectName": "股东变更",
                        "BeforeContent": "原股东",
                        "AfterContent": "测试股东",
                    },
                    {
                        "ChangeDate": "2025-01-03",
                        "ProjectName": "地址变更",
                        "BeforeContent": "甲地",
                        "AfterContent": "乙地",
                    },
                ],
            },
        }
        equity = professional.parse_qcc_company(payload, self.company.name)
        self.assertEqual(equity["legalName"], "智元创新（上海）科技股份有限公司")
        self.assertEqual(equity["shareholders"][0]["percent"], "31.5%")
        self.assertEqual(equity["beneficialOwners"][0]["name"], "测试股东")
        self.assertEqual(len(equity["changes"]), 1)
        self.assertEqual(equity["changes"][0]["item"], "股东变更")
        self.assertIn("qcc.com", equity["shareholders"][0]["sourceUrl"])

    def test_qcc_financing_parser_preserves_round_amount_and_investors(self) -> None:
        payload = {
            "Result": {
                "Data": [
                    {
                        "Date": "2025-03-18",
                        "ProductName": "智元机器人",
                        "Round": "A轮",
                        "Amount": "10亿元人民币",
                        "Valuation": "100亿元人民币",
                        "Investment": "红杉中国、测试资本",
                        "NewsUrl": "https://example.com/original-disclosure",
                    }
                ]
            }
        }
        rows = professional.parse_qcc_financing(payload, self.company.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round"], "A轮")
        self.assertEqual(rows[0]["amount"], "10亿元人民币")
        self.assertEqual(rows[0]["investors"], ["红杉中国", "测试资本"])
        self.assertEqual(rows[0]["sourceUrl"], "https://example.com/original-disclosure")

    def test_tianyancha_parsers_extract_holders_changes_and_beneficiaries(self) -> None:
        holders = professional.parse_tyc_holders(
            {
                "result": {
                    "items": [
                        {
                            "shareholderName": "测试创始人",
                            "shareholdingRatio": "45%",
                            "subscribedAmount": "450万元人民币",
                            "paidAmount": "300万元人民币",
                        }
                    ]
                }
            },
            self.company.name,
        )
        changes = professional.parse_tyc_changes(
            {
                "result": {
                    "holderChangeList": [
                        {
                            "changeDate": "2025-02-01",
                            "holderName": "测试创始人",
                            "beforePercent": "50%",
                            "afterPercent": "45%",
                        }
                    ]
                }
            },
            self.company.name,
        )
        beneficiaries = professional.parse_tyc_beneficiaries(
            {
                "result": {
                    "list": [
                        {
                            "humanName": "测试创始人",
                            "totalPercent": "45%",
                            "relation": "最终受益人",
                        }
                    ]
                }
            },
            self.company.name,
        )
        self.assertEqual(holders[0]["name"], "测试创始人")
        self.assertEqual(changes[0]["after"], "45%")
        self.assertEqual(beneficiaries[0]["relationship"], "最终受益人")
        self.assertTrue(all("tianyancha.com" in row["sourceUrl"] for row in [*holders, *changes, *beneficiaries]))

    def test_jingdata_discovery_accepts_only_identity_matched_public_pages(self) -> None:
        rss = """<?xml version="1.0" encoding="utf-8"?>
        <rss><channel>
          <item>
            <title>智元机器人完成A轮融资</title>
            <link>https://www.jingdata.com/project/agibot</link>
            <description>智元机器人于2025-03-18完成10亿元人民币A轮融资。</description>
          </item>
          <item>
            <title>另一家公司完成B轮融资</title>
            <link>https://www.jingdata.com/project/other</link>
            <description>另一家公司融资。</description>
          </item>
          <item>
            <title>智元机器人完成融资</title>
            <link>https://aggregator.example.com/agibot</link>
            <description>第三方聚合页。</description>
          </item>
        </channel></rss>"""
        rows, status = professional.discover_jingdata_financing(
            self.company,
            fetcher=lambda url: rss,
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["round"], "A轮")
        self.assertEqual(rows[0]["amount"], "10亿元")
        self.assertEqual(rows[0]["verification"], "待交叉验证")
        self.assertEqual(status["status"], "success")

    def test_equity_merge_combines_sources_without_overwriting_existing_facts(self) -> None:
        merged = professional.merge_equity_profiles(
            {
                "legalName": "既有法定名称",
                "shareholders": [
                    {
                        "name": "测试股东",
                        "percent": "30%",
                        "sourceName": "企查查",
                        "sourceUrl": "https://www.qcc.com/web/search?key=test",
                    }
                ],
                "sourceNames": ["企查查"],
                "sourceUrls": ["https://www.qcc.com/web/search?key=test"],
            },
            [
                {
                    "legalName": "另一名称",
                    "shareholders": [
                        {
                            "name": "测试股东",
                            "subscribedCapital": "300万元人民币",
                            "sourceName": "天眼查",
                            "sourceUrl": "https://www.tianyancha.com/search?key=test",
                        }
                    ],
                    "sourceNames": ["天眼查"],
                    "sourceUrls": ["https://www.tianyancha.com/search?key=test"],
                }
            ],
        )
        self.assertEqual(merged["legalName"], "既有法定名称")
        self.assertEqual(merged["shareholders"][0]["percent"], "30%")
        self.assertEqual(
            merged["shareholders"][0]["subscribedCapital"],
            "300万元人民币",
        )
        self.assertEqual(merged["evidenceStatus"], "cross-verified")

    def test_paid_sources_stay_disabled_without_explicit_opt_in(self) -> None:
        profile, statuses = professional.enrich_company(
            self.company,
            {"slug": "agibot", "name": "智元机器人", "sources": [], "financing": []},
            paid_enabled=False,
            qcc_app_key="configured-but-disabled",
            qcc_secret_key="configured-but-disabled",
            tyc_token="configured-but-disabled",
            public_discovery=False,
            include_external_investments=False,
            include_beneficiaries=False,
            qcc_fetcher=lambda *args, **kwargs: self.fail("QCC paid API must not be called"),
            tyc_fetcher=lambda *args, **kwargs: self.fail("Tianyancha paid API must not be called"),
        )
        self.assertEqual(
            [(row["name"], row["status"]) for row in statuses],
            [("企查查", "disabled"), ("天眼查", "disabled"), ("鲸准", "disabled")],
        )
        self.assertEqual(profile["equityProfile"]["evidenceStatus"], "pending")


if __name__ == "__main__":
    unittest.main()
