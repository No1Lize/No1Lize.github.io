import json
import unittest

from tools import crawl_market_profiles as market
from tools import market_profile_enrichment as enrichment


class MarketProfileEnrichmentTests(unittest.TestCase):
    def test_quote_payload_adds_market_cap_and_trading_metrics(self):
        payload = json.dumps(
            {
                "data": {
                    "f116": 1_234_500_000_000,
                    "f117": 987_600_000_000,
                    "f84": 1_000_000_000,
                    "f85": 800_000_000,
                    "f162": 2534,
                    "f167": 481,
                    "f168": 267,
                    "f48": 3_250_000_000,
                }
            }
        )
        result = enrichment.parse_quote_payload(payload, "A股")
        metrics = {item["id"]: item["value"] for item in result["metrics"]}
        self.assertEqual(metrics["marketCap"], "¥1.23万亿")
        self.assertEqual(metrics["floatMarketCap"], "¥9876.00亿")
        self.assertEqual(metrics["totalShares"], "10.00亿股")
        self.assertEqual(metrics["pe"], "25.34")
        self.assertEqual(metrics["pb"], "4.81")
        self.assertEqual(metrics["turnover"], "2.67%")

    def test_region_is_inferred_from_address_and_market(self):
        a_identity = market.company_identity("A股", "600519")
        hk_identity = market.company_identity("港股", "0700")
        us_identity = market.company_identity("美股", "AAPL")
        self.assertIsNotNone(a_identity)
        self.assertEqual(
            enrichment.infer_region(
                {"company": {"address": "贵州省遵义市仁怀市茅台镇"}},
                a_identity,
            ),
            "贵州",
        )
        self.assertEqual(enrichment.infer_region({"company": {}}, hk_identity), "中国香港")
        self.assertEqual(enrichment.infer_region({"company": {}}, us_identity), "美国")

    def test_description_removes_award_tail_and_closes_sentence(self):
        raw = (
            "公司主营人工智能芯片研发、设计与销售，产品覆盖云端、边缘和终端设备。"
            "公司成立至今共获得多项荣誉：2018年获得某奖项，2019年入选某榜单。"
        )
        normalized = enrichment.normalize_company_text(raw, 180)
        self.assertIn("人工智能芯片", normalized)
        self.assertNotIn("多项荣誉", normalized)
        self.assertTrue(normalized.endswith("。"))

    def test_market_cap_can_be_derived_from_shares_and_close(self):
        identity = market.company_identity("港股", "0700")
        profile = {
            "company": {"name": "腾讯控股"},
            "metrics": [{"id": "totalShares", "label": "总股本", "value": "95.00亿股"}],
            "priceHistory": [{"date": "2026-07-24", "close": 500.0}],
        }
        metric = enrichment.infer_market_cap(profile, identity)
        self.assertEqual(metric["id"], "marketCap")
        self.assertEqual(metric["value"], "HK$4.75万亿")

    def test_enrichment_replaces_unit_only_market_cap(self):
        identity = market.company_identity("美股", "AAPL")
        profile = {
            "company": {"name": "Apple", "description": "消费电子与软件服务。"},
            "metrics": [{"id": "marketCap", "label": "总市值", "value": "亿"}],
            "priceHistory": [],
            "sources": {},
        }
        body = json.dumps({"data": {"f116": 3_200_000_000_000}})
        enriched = enrichment.enrich_profile(identity, profile, lambda _: body)
        metrics = {item["id"]: item["value"] for item in enriched["metrics"]}
        self.assertEqual(metrics["marketCap"], "US$3.20万亿")
        self.assertEqual(enriched["company"]["region"], "美国")


if __name__ == "__main__":
    unittest.main()
