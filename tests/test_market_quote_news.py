import json
import unittest
from datetime import date
from pathlib import Path

from tools import crawl_market_profiles as market
from tools import market_quote_news_sources as quote_news


ROOT = Path(__file__).resolve().parents[1]

YAHOO_QUOTE_BODY = json.dumps(
    {
        "chart": {
            "result": [
                {
                    "meta": {
                        "currency": "USD",
                        "symbol": "PONY",
                        "exchangeName": "NMS",
                        "regularMarketPrice": 13.45,
                        "chartPreviousClose": 12.9,
                        "regularMarketTime": 1784947800,
                    }
                }
            ],
            "error": None,
        }
    }
)

YAHOO_RSS_BODY = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Yahoo! Finance</title>
<item>
  <title><![CDATA[Pony AI expands robotaxi fleet in Singapore]]></title>
  <link>https://finance.yahoo.com/news/pony-ai-expands.html</link>
  <pubDate>Fri, 24 Jul 2026 08:30:00 +0000</pubDate>
</item>
<item>
  <title>Off-domain partner headline that must be dropped</title>
  <link>https://example.com/partner-post</link>
  <pubDate>Fri, 24 Jul 2026 09:00:00 +0000</pubDate>
</item>
<item>
  <title>Second allowed headline</title>
  <link>https://sg.finance.yahoo.com/news/second.html</link>
  <pubDate>Thu, 23 Jul 2026 02:00:00 +0000</pubDate>
</item>
</channel></rss>
"""


def sina_a_quote_body():
    fields = ["寒武纪", "780.000", "779.000", "781.550", "790.000", "770.100"]
    fields += ["781.500", "781.550", "12345678", "9640000000.000"]
    fields += [str(index) for index in range(10, 30)]
    fields += ["2026-07-24", "15:00:03", "00"]
    return f'var hq_str_sh688256="{",".join(fields)}";'


SINA_HK_QUOTE_BODY = (
    'var hq_str_rt_hk09660="HORIZONROBOT-W,地平线机器人-W,7.900,7.850,8.010,7.820,'
    '7.950,0.100,1.274,7.940,7.950,876543210.500,110234567,0.000,0.000,9.700,3.900,'
    '2026/07/24,16:08:44";'
)


# 与线上 vCB_AllNewsStock 页面一致：日期与时间之间是 &nbsp; 分隔。
SINA_A_NEWS_BODY = """
<div class="datelist"><ul>
&nbsp;&nbsp;&nbsp;&nbsp;2026-07-24&nbsp;19:04&nbsp;&nbsp;<a target='_blank' href='https://finance.sina.com.cn/stock/relnews/cn/2026-07-24/doc-abc.shtml'>寒武纪发布新一代云端智能训练芯片</a> <br>
&nbsp;&nbsp;2026-07-23 08:15&nbsp;&nbsp;<a href='https://finance.sina.com.cn/roll/2026-07-23/doc-xyz.shtml' target='_blank'>寒武纪中标某智算中心大额订单</a><br>
&nbsp;&nbsp;2026-07-22&nbsp;10:00&nbsp;&nbsp;<a href='https://evil.example.com/doc.shtml' target='_blank'>不在白名单域名下的标题应被丢弃</a><br>
</ul></div>
"""

SINA_HK_NEWS_BODY = """
<ul class="list01">
<li><a target="_blank" href="https://stock.finance.sina.com.cn/hkstock/go.php/CompanyNewsContent/page/1/code/09660/id/123.phtml">地平线机器人获纳入港股通标的名单</a><span>(07-20 16:30)</span></li>
<li><a target="_blank" href="https://stock.finance.sina.com.cn/hkstock/go.php/CompanyNewsContent/page/1/code/09660/id/456.phtml">地平线机器人发布中期业绩公告摘要</a><span>(12-31 09:00)</span></li>
</ul>
"""


def make_fetcher(mapping, calls=None):
    def fetch(url, referer=""):
        if calls is not None:
            calls.append((url, referer))
        for key, value in mapping.items():
            if key in url:
                if isinstance(value, Exception):
                    raise value
                return value
        raise AssertionError(f"unexpected URL {url}")

    return fetch


class SymbolTests(unittest.TestCase):
    def test_yahoo_symbols_for_three_markets(self):
        us = market.company_identity("美股", "PONY")
        hk = market.company_identity("港股", "09660")
        hk_short = market.company_identity("港股", "700")
        a = market.company_identity("A股", "688256")
        self.assertEqual(quote_news.yahoo_symbol(us), "PONY")
        self.assertEqual(quote_news.yahoo_symbol(hk), "9660.HK")
        self.assertEqual(quote_news.yahoo_symbol(hk_short), "0700.HK")
        self.assertEqual(quote_news.yahoo_symbol(a), "")

    def test_sina_codes_and_public_page_urls(self):
        a = market.company_identity("A股", "688256")
        sz = market.company_identity("A股", "300750")
        hk = market.company_identity("港股", "09660")
        us = market.company_identity("美股", "PONY")
        self.assertEqual(quote_news.sina_quote_code(a), "sh688256")
        self.assertEqual(quote_news.sina_quote_code(sz), "sz300750")
        self.assertEqual(quote_news.sina_quote_code(hk), "rt_hk09660")
        self.assertEqual(quote_news.sina_quote_code(us), "")
        self.assertEqual(
            quote_news.sina_page_url(a),
            "https://finance.sina.com.cn/realstock/company/sh688256/nc.shtml",
        )
        self.assertEqual(
            quote_news.sina_page_url(hk),
            "https://stock.finance.sina.com.cn/hkstock/quotes/09660.html",
        )
        self.assertEqual(
            quote_news.yahoo_page_url("9660.HK"),
            "https://sg.finance.yahoo.com/quote/9660.HK/",
        )
        self.assertIn(
            "vCB_AllNewsStock/symbol/sh688256.phtml", quote_news.sina_news_url(a)
        )
        self.assertIn("CompanyNews/page/1/code/09660/", quote_news.sina_news_url(hk))


class YahooParserTests(unittest.TestCase):
    def test_yahoo_quote_meta_parsing_computes_change(self):
        quote = quote_news.parse_yahoo_quote(YAHOO_QUOTE_BODY)
        self.assertEqual(quote["price"], 13.45)
        self.assertEqual(quote["previousClose"], 12.9)
        self.assertEqual(quote["change"], 0.55)
        self.assertEqual(quote["changePercent"], 4.26)
        self.assertEqual(quote["currency"], "USD")
        self.assertTrue(quote["asOf"].startswith("20"))

    def test_yahoo_quote_rejects_missing_price(self):
        body = json.dumps({"chart": {"result": [{"meta": {"currency": "USD"}}]}})
        self.assertEqual(quote_news.parse_yahoo_quote(body), {})

    def test_yahoo_rss_keeps_only_yahoo_hosts_with_iso_times(self):
        items = quote_news.parse_yahoo_news(YAHOO_RSS_BODY)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "Pony AI expands robotaxi fleet in Singapore")
        self.assertEqual(items[0]["url"], "https://finance.yahoo.com/news/pony-ai-expands.html")
        self.assertEqual(items[0]["publishedAt"], "2026-07-24T08:30:00+00:00")
        self.assertEqual(items[0]["source"], "Yahoo财经")
        self.assertTrue(all("example.com" not in item["url"] for item in items))


class SinaParserTests(unittest.TestCase):
    def test_a_share_quote_line_parses_price_change_and_time(self):
        quote = quote_news.parse_sina_quote(sina_a_quote_body(), "A股")
        self.assertEqual(quote["price"], 781.55)
        self.assertEqual(quote["previousClose"], 779.0)
        self.assertEqual(quote["change"], 2.55)
        self.assertEqual(quote["changePercent"], 0.33)
        self.assertEqual(quote["currency"], "CNY")
        self.assertEqual(quote["asOf"], "2026-07-24T15:00:03+08:00")

    def test_hk_quote_line_parses_native_change_columns(self):
        quote = quote_news.parse_sina_quote(SINA_HK_QUOTE_BODY, "港股")
        self.assertEqual(quote["price"], 7.95)
        self.assertEqual(quote["previousClose"], 7.85)
        self.assertEqual(quote["change"], 0.1)
        self.assertEqual(quote["changePercent"], 1.27)
        self.assertEqual(quote["currency"], "HKD")
        self.assertEqual(quote["asOf"], "2026-07-24T16:08:44+08:00")

    def test_suspended_zero_price_yields_no_quote(self):
        fields = ["停牌股", "0.000", "10.000", "0.000", "0.000", "0.000"]
        body = f'var hq_str_sh600000="{",".join(fields)}";'
        self.assertEqual(quote_news.parse_sina_quote(body, "A股"), {})

    def test_a_share_news_list_extracts_dated_titles_within_allowlist(self):
        items = quote_news.parse_sina_news(SINA_A_NEWS_BODY, today=date(2026, 7, 24))
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["title"], "寒武纪发布新一代云端智能训练芯片")
        self.assertEqual(items[0]["publishedAt"], "2026-07-24T19:04:00+08:00")
        self.assertEqual(items[0]["source"], "新浪财经")
        self.assertTrue(all("evil.example.com" not in item["url"] for item in items))

    def test_hk_news_list_resolves_short_dates_across_year_boundary(self):
        items = quote_news.parse_sina_news(SINA_HK_NEWS_BODY, today=date(2026, 7, 24))
        by_title = {item["title"]: item for item in items}
        self.assertEqual(
            by_title["地平线机器人获纳入港股通标的名单"]["publishedAt"],
            "2026-07-20T16:30:00+08:00",
        )
        # 12-31 尚未到来，短日期必须回落到上一年，不允许伪造未来时间。
        self.assertEqual(
            by_title["地平线机器人发布中期业绩公告摘要"]["publishedAt"],
            "2025-12-31T09:00:00+08:00",
        )


class MergeTests(unittest.TestCase):
    def test_merge_news_dedupes_and_sorts_newest_first(self):
        yahoo = [
            {"title": "Same story", "url": "https://finance.yahoo.com/news/a.html",
             "publishedAt": "2026-07-24T08:30:00+00:00", "source": "Yahoo财经"},
        ]
        sina = [
            {"title": "Same Story", "url": "https://finance.sina.com.cn/doc-b.shtml",
             "publishedAt": "2026-07-24T18:30:00+08:00", "source": "新浪财经"},
            {"title": "更晚的独立新闻", "url": "https://finance.sina.com.cn/doc-c.shtml",
             "publishedAt": "2026-07-25T09:00:00+08:00", "source": "新浪财经"},
        ]
        merged = quote_news.merge_news(yahoo, sina)
        self.assertEqual(len(merged), 2)  # 标题去重（大小写与空白无关）
        self.assertEqual(merged[0]["title"], "更晚的独立新闻")
        self.assertEqual(merged[1]["source"], "Yahoo财经")

    def test_merge_news_caps_item_count(self):
        many = [
            {"title": f"标题{index}", "url": f"https://finance.sina.com.cn/{index}.shtml",
             "publishedAt": f"2026-07-{index + 1:02d}T09:00:00+08:00", "source": "新浪财经"}
            for index in range(15)
        ]
        self.assertEqual(len(quote_news.merge_news(many)), quote_news.MAX_NEWS_ITEMS)


class EnrichmentTests(unittest.TestCase):
    def test_a_share_uses_sina_quote_and_news_with_referer(self):
        identity = market.company_identity("A股", "688256")
        calls = []
        fetcher = make_fetcher(
            {
                "hq.sinajs.cn/list=sh688256": sina_a_quote_body(),
                "vCB_AllNewsStock/symbol/sh688256": SINA_A_NEWS_BODY,
            },
            calls,
        )
        profile = quote_news.enrich_quote_and_news(identity, {"sources": {}}, {}, fetcher)
        self.assertEqual(profile["quote"]["price"], 781.55)
        self.assertEqual(profile["quote"]["source"]["name"], "新浪财经")
        self.assertEqual(
            profile["quote"]["source"]["url"],
            "https://finance.sina.com.cn/realstock/company/sh688256/nc.shtml",
        )
        self.assertEqual(len(profile["news"]), 2)
        self.assertEqual(profile["news"][0]["source"], "新浪财经")
        self.assertIn("sinaFinance", profile["sources"])
        self.assertNotIn("yahooFinance", profile["sources"])
        for url, referer in calls:
            if "sinajs" in url or "sina.com.cn" in url:
                self.assertEqual(referer, "https://finance.sina.com.cn/")

    def test_us_company_uses_yahoo_quote_and_news(self):
        identity = market.company_identity("美股", "PONY")
        fetcher = make_fetcher(
            {
                "query1.finance.yahoo.com/v8/finance/chart/PONY": YAHOO_QUOTE_BODY,
                "feeds.finance.yahoo.com/rss/2.0/headline?s=PONY": YAHOO_RSS_BODY,
            }
        )
        profile = quote_news.enrich_quote_and_news(identity, {}, {}, fetcher)
        self.assertEqual(profile["quote"]["price"], 13.45)
        self.assertEqual(profile["quote"]["source"]["name"], "Yahoo财经")
        self.assertEqual(
            profile["sources"]["yahooFinance"],
            "https://sg.finance.yahoo.com/quote/PONY/",
        )
        self.assertNotIn("sinaFinance", profile["sources"])
        self.assertEqual(len(profile["news"]), 2)
        self.assertTrue(all(item["source"] == "Yahoo财经" for item in profile["news"]))

    def test_hk_company_merges_both_sources_and_falls_back_to_yahoo_quote(self):
        identity = market.company_identity("港股", "09660")
        fetcher = make_fetcher(
            {
                "hq.sinajs.cn/list=rt_hk09660": RuntimeError("sina quote blocked"),
                "query1.finance.yahoo.com/v8/finance/chart/9660.HK": YAHOO_QUOTE_BODY,
                "feeds.finance.yahoo.com/rss/2.0/headline?s=9660.HK": YAHOO_RSS_BODY,
                "CompanyNews/page/1/code/09660/": SINA_HK_NEWS_BODY,
            }
        )
        profile = quote_news.enrich_quote_and_news(identity, {}, {}, fetcher)
        self.assertEqual(profile["quote"]["source"]["name"], "Yahoo财经")
        news_sources = {item["source"] for item in profile["news"]}
        self.assertEqual(news_sources, {"Yahoo财经", "新浪财经"})
        self.assertIn("yahooFinance", profile["sources"])
        self.assertIn("sinaFinance", profile["sources"])
        self.assertTrue(
            any("新浪财经行情" in warning for warning in profile.get("warnings", []))
        )

    def test_total_failure_preserves_previous_quote_and_news(self):
        identity = market.company_identity("A股", "688256")

        def always_fail(url, referer=""):
            raise RuntimeError("network unavailable")

        previous = {
            "quote": {
                "price": 700.0,
                "currency": "CNY",
                "source": {"name": "新浪财经", "url": "https://finance.sina.com.cn/x"},
            },
            "news": [
                {
                    "title": "上一轮保留的标题",
                    "url": "https://finance.sina.com.cn/doc-old.shtml",
                    "publishedAt": "2026-07-20T09:00:00+08:00",
                    "source": "新浪财经",
                }
            ],
        }
        profile = quote_news.enrich_quote_and_news(identity, {}, previous, always_fail)
        self.assertEqual(profile["quote"], previous["quote"])
        self.assertEqual(profile["news"], previous["news"])
        self.assertTrue(any("保留上一轮" in warning for warning in profile["warnings"]))

    def test_failure_without_previous_data_never_fabricates(self):
        identity = market.company_identity("美股", "PONY")

        def always_fail(url, referer=""):
            raise RuntimeError("network unavailable")

        profile = quote_news.enrich_quote_and_news(identity, {}, {}, always_fail)
        self.assertNotIn("quote", profile)
        self.assertNotIn("news", profile)
        self.assertTrue(profile["warnings"])


class MarketRefreshScheduleTests(unittest.TestCase):
    def test_market_profile_refresh_is_an_explicit_maintenance_task(self):
        text = (ROOT / ".github" / "workflows" / "market-profile-refresh.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("  schedule:", text)
        self.assertNotIn("  push:", text)
        self.assertIn("tests.test_market_quote_news", text)

    def test_scheduled_sync_watches_quote_news_module(self):
        text = (ROOT / ".github" / "workflows" / "scheduled-sync.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("tools/market_quote_news_sources.py", text)


if __name__ == "__main__":
    unittest.main()
