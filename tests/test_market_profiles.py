import json
import unittest

from tools import crawl_market_profiles as market


A_HTML = """
<html><head><title>贵州茅台(600519)首页概览_同花顺</title></head><body>
<div>公司名称：贵州茅台酒股份有限公司</div>
<div>上市日期：2001-08-27</div><div>所属行业：白酒</div>
<div>董事长：张德芹</div><div>员工人数：32000</div>
<div>公司网址：www.moutaichina.com</div>
<div>主营业务：茅台酒及系列酒的生产与销售。</div>
<div>总股本：12.50亿股</div><div>每股收益：21.76元</div>
<div>净利润：272.43亿元</div><div>营业收入：547.03亿元</div>
[[[0,"862.28"],[1,"272.43"]],[[0,"2025年报"],[1,"2026一季报"]],"亿元"] 净利润
[[[0,"1741.44"],[1,"547.03"]],[[0,"2025年报"],[1,"2026一季报"]],"亿元"] 营业收入
</body></html>
"""

HK_HTML = """
<html lang="zh-HK"><head><title>腾讯控股(00700)首页概览_同花顺</title></head><body>
<div>公司名称：腾讯控股有限公司</div><div>英文名称：Tencent Holdings Ltd.</div>
<div>上市日期：2004-06-16</div><div>所属行业：资讯科技业 - 软件服务</div>
<div>交易所：香港交易所主板</div><div>董事长：马化腾</div>
<div>公司网址：www.tencent.com</div><div>员工人数：115849</div>
<div>主营业务：提供增值服务、营销服务以及金融科技及企业服务。</div>
<div>每股收益：6.43元</div><div>净利润：593.92亿元</div>
<div>营业收入：1964.58亿元</div>
[[[0,"497.25"],[1,"593.92"]],[[0,"2025一季报"],[1,"2026一季报"]],"亿元"] 净利润
[[[0,"1800.22"],[1,"1964.58"]],[[0,"2025一季报"],[1,"2026一季报"]],"亿元"] 营业收入
</body></html>
"""

US_HTML = """
<html lang="en"><head><title>苹果(AAPL)首页概览_同花顺</title></head><body>
<div>公司名称：苹果公司</div><div>英文名称：Apple Inc.</div>
<div>上市日期：1980-12-12</div><div>所属行业：电脑硬件</div>
<div>交易所：美国NASDAQ证券交易所</div><div>员工人数：166000</div>
<div>公司网址：www.apple.com</div>
<div>公司简介：设计、制造和销售智能手机、个人电脑、平板电脑及相关服务。</div>
<div>每股收益：4.87美元</div><div>净利润：716.75亿美元</div>
<div>营业收入：2549.40亿美元</div>
[[[0,"611.10"],[1,"716.75"]],[[0,"2025中报"],[1,"2026中报"]],"亿美元"] 净利润
[[[0,"2196.59"],[1,"2549.40"]],[[0,"2025中报"],[1,"2026中报"]],"亿美元"] 营业收入
</body></html>
"""


def kline_payload(code):
    return json.dumps(
        {
            "data": {
                code: {
                    "qfqday": [
                        ["2026-07-21", "100", "101", "102", "99", "1000"],
                        ["2026-07-22", "101", "103", "104", "100", "1200"],
                        ["2026-07-23", "103", "102", "105", "101", "1100"],
                    ]
                }
            }
        }
    )


class MarketProfileTests(unittest.TestCase):
    def test_three_market_identity_normalization(self):
        a = market.company_identity("A股", "600519.SH")
        hk = market.company_identity("港股", "HK0700")
        hk_suffix = market.company_identity("港股", "0700.HK")
        us = market.company_identity("美股", "aapl")

        self.assertEqual((a.ticker, a.slug, a.ths_code, a.quote_code), ("600519", "a-600519", "600519", "sh600519"))
        self.assertEqual((hk.ticker, hk.slug, hk.ths_code, hk.quote_code), ("00700", "hk-00700", "HK0700", "hk00700"))
        self.assertEqual(hk, hk_suffix)
        self.assertEqual((us.ticker, us.slug, us.ths_code, us.quote_code), ("AAPL", "us-aapl", "AAPL", "usAAPL"))

    def test_tonghuashun_parser_extracts_profile_metrics_and_series(self):
        identity = market.company_identity("港股", "700")
        parsed = market.parse_tonghuashun_html(HK_HTML, identity, "腾信控股")
        self.assertTrue(parsed["accepted"])
        self.assertEqual(parsed["company"]["name"], "腾讯控股有限公司")
        self.assertEqual(parsed["company"]["listedAt"], "2004-06-16")
        self.assertEqual(parsed["company"]["exchange"], "香港交易所主板")
        self.assertIn("营业收入", {item["label"] for item in parsed["metrics"]})
        self.assertEqual({item["id"] for item in parsed["financialSeries"]}, {"netIncome", "revenue"})

    def test_backend_addition_creates_all_three_market_profiles(self):
        config = {
            "listedCompanies": [
                {"name": "贵州茅台", "ticker": "600519.SH", "market": "A股", "sector": "消费", "enabled": True},
                {"name": "腾信控股", "ticker": "0700.HK", "market": "港股", "sector": "AI / AGI", "enabled": True},
                {"name": "苹果公司", "ticker": "aapl", "market": "美股", "sector": "消费电子", "enabled": True},
            ]
        }

        html_by_code = {"600519": A_HTML, "HK0700": HK_HTML, "AAPL": US_HTML}

        def fake_fetch(url):
            if "stockpage.10jqka.com.cn" in url:
                code = url.rstrip("/").rsplit("/", 1)[-1]
                return html_by_code[code]
            for quote_code in ("sh600519", "hk00700", "usAAPL"):
                if quote_code in url:
                    return kline_payload(quote_code)
            raise AssertionError(f"unexpected URL {url}")

        snapshot = market.build_snapshot(config, {"profiles": {}}, fake_fetch)
        self.assertEqual(set(snapshot["profiles"]), {"a-600519", "hk-00700", "us-aapl"})
        self.assertEqual(snapshot["profiles"]["hk-00700"]["company"]["name"], "腾讯控股有限公司")
        self.assertEqual(snapshot["profiles"]["us-aapl"]["ticker"], "AAPL")
        self.assertEqual(len(snapshot["profiles"]["a-600519"]["priceHistory"]), 3)
        self.assertTrue(all(row["status"] == "ok" for row in snapshot["sourceStatus"]))

    def test_previous_snapshot_survives_ambiguous_failure(self):
        config = {
            "listedCompanies": [
                {"name": "苹果公司", "ticker": "AAPL", "market": "美股", "sector": "消费电子", "enabled": True}
            ]
        }
        previous = {
            "profiles": {
                "us-aapl": {
                    "company": {"name": "苹果公司", "industry": "电脑硬件"},
                    "priceHistory": [
                        {"date": "2026-07-20", "open": 100, "close": 101, "high": 102, "low": 99}
                    ],
                    "metrics": [{"id": "eps", "label": "每股收益", "value": "4.87美元"}],
                    "financialSeries": [],
                }
            }
        }

        def failed_fetch(_url):
            raise RuntimeError("temporary block")

        snapshot = market.build_snapshot(config, previous, failed_fetch)
        profile = snapshot["profiles"]["us-aapl"]
        self.assertEqual(profile["priceHistory"], previous["profiles"]["us-aapl"]["priceHistory"])
        self.assertEqual(profile["metrics"], previous["profiles"]["us-aapl"]["metrics"])
        self.assertEqual(profile["status"], "partial")


if __name__ == "__main__":
    unittest.main()
