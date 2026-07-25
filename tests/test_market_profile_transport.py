import json
import unittest

from tools import crawl_market_profiles as market
from tools import refresh_market_profiles as refresh


class MarketProfileTransportTests(unittest.TestCase):
    def test_table_style_labels_without_colons_are_supported(self):
        text = "公司名称\n腾讯控股有限公司\n上市日期\n2004-06-16\n所属行业 软件服务"
        self.assertEqual(
            refresh.robust_labeled_value(text, ["公司名称"], 100),
            "腾讯控股有限公司",
        )
        self.assertEqual(
            refresh.robust_labeled_value(text, ["上市日期"], 40),
            "2004-06-16",
        )
        self.assertEqual(
            refresh.robust_labeled_value(text, ["所属行业"], 100),
            "软件服务",
        )

    def test_only_company_roots_trigger_multi_page_expansion(self):
        self.assertTrue(
            refresh.is_tonghuashun_company_root(
                "https://stockpage.10jqka.com.cn/HK0700/"
            )
        )
        self.assertFalse(
            refresh.is_tonghuashun_company_root(
                "https://stockpage.10jqka.com.cn/HK0700/finance/"
            )
        )
        self.assertFalse(
            refresh.is_tonghuashun_company_root(
                "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
            )
        )

    def test_a_share_routes_include_index_company_finance_operate_and_youth(self):
        pages = refresh.tonghuashun_pages(
            "https://stockpage.10jqka.com.cn/600519/"
        )
        self.assertEqual(pages[0], "https://stockpage.10jqka.com.cn/600519/")
        self.assertIn("https://stockpage.10jqka.com.cn/600519/index/", pages)
        self.assertIn("https://stockpage.10jqka.com.cn/600519/company/", pages)
        self.assertIn("https://stockpage.10jqka.com.cn/600519/finance/", pages)
        self.assertIn("https://stockpage.10jqka.com.cn/600519/operate/", pages)
        self.assertIn("https://stockpage.10jqka.com.cn/youth/600519/", pages)
        self.assertNotIn(
            "https://stockpage.10jqka.com.cn/youth/HK0700/",
            refresh.tonghuashun_pages(
                "https://stockpage.10jqka.com.cn/HK0700/"
            ),
        )

    def test_eastmoney_market_mapping_and_kline_shape(self):
        identity = market.company_identity("美股", "AAPL")
        self.assertEqual(
            refresh.eastmoney_market_ids("美国NASDAQ证券交易所"),
            [105, 106, 107],
        )
        self.assertEqual(
            refresh.eastmoney_market_ids("美国纽约证券交易所"),
            [106, 105, 107],
        )
        self.assertIn("secid=105.AAPL", refresh.eastmoney_url(identity, 105))
        payload = json.dumps(
            {
                "data": {
                    "klines": [
                        "2026-07-21,210,213,214,209,1000",
                        "2026-07-22,213,215,216,212,1200",
                    ]
                }
            }
        )
        self.assertEqual(
            refresh.parse_eastmoney_kline(payload),
            [
                {
                    "date": "2026-07-21",
                    "open": 210.0,
                    "close": 213.0,
                    "high": 214.0,
                    "low": 209.0,
                    "volume": 1000.0,
                },
                {
                    "date": "2026-07-22",
                    "open": 213.0,
                    "close": 215.0,
                    "high": 216.0,
                    "low": 212.0,
                    "volume": 1200.0,
                },
            ],
        )

    def test_stooq_csv_provides_full_us_trend_shape(self):
        body = """Date,Open,High,Low,Close,Volume
2026-07-21,210,214,209,213,1000
2026-07-22,213,216,212,215,1200
"""
        self.assertEqual(
            refresh.parse_stooq_csv(body),
            [
                {
                    "date": "2026-07-21",
                    "open": 210.0,
                    "close": 213.0,
                    "high": 214.0,
                    "low": 209.0,
                    "volume": 1000.0,
                },
                {
                    "date": "2026-07-22",
                    "open": 213.0,
                    "close": 215.0,
                    "high": 216.0,
                    "low": 212.0,
                    "volume": 1200.0,
                },
            ],
        )
        identity = market.company_identity("美股", "AAPL")
        self.assertEqual(
            refresh.stooq_url(identity),
            "https://stooq.com/q/d/l/?s=aapl.us&i=d",
        )

    def test_market_cleaning_removes_pre_listing_points_and_double_percent(self):
        profile = {
            "company": {"name": "文远知行", "listedAt": "2024-10-25"},
            "metrics": [
                {"id": "roe", "label": "净资产收益率", "value": "4.56%%"}
            ],
            "priceHistory": [
                {
                    "date": "2011-06-02",
                    "open": 23.3,
                    "close": 23.3,
                    "high": 23.48,
                    "low": 23.29,
                },
                {
                    "date": "2026-07-24",
                    "open": 5.67,
                    "close": 5.32,
                    "high": 5.67,
                    "low": 5.32,
                },
            ],
        }
        cleaned = refresh.clean_profile(profile)
        self.assertEqual(cleaned["metrics"][0]["value"], "4.56%")
        self.assertEqual(
            [point["date"] for point in cleaned["priceHistory"]],
            ["2026-07-24"],
        )


if __name__ == "__main__":
    unittest.main()
