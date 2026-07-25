import unittest

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


if __name__ == "__main__":
    unittest.main()
