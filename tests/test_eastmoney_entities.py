import unittest

from tools.eastmoney_entities import (
    attribute_eastmoney_article,
    extract_eastmoney_linked_tickers,
)


DETAIL_URL = "https://finance.eastmoney.com/a/202607253821103130.html"


def article(title: str, summary: str = "") -> dict:
    return {
        "title": title,
        "summary": summary,
        "company": "科技产业",
        "sector": "AI / AGI",
        "region": "全球",
        "source": {
            "name": "东方财富",
            "url": DETAIL_URL,
            "level": "媒体报道",
            "platform": "东方财富",
        },
    }


def entity(
    name: str,
    ticker: str,
    sector: str,
    slug: str,
    market: str = "A股",
) -> dict[str, str]:
    return {
        "id": f"catalog-{slug}",
        "name": name,
        "englishName": "",
        "ticker": ticker,
        "market": market,
        "sector": sector,
        "catalogSlug": slug,
    }


class EastmoneyEntityEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cambricon = entity("寒武纪", "688256", "半导体", "cambricon")
        self.catl = entity("宁德时代", "300750", "新能源", "catl")
        self.ionq = entity("IonQ", "IONQ", "量子计算", "ionq", market="美股")

    def test_unique_summary_company_is_used_when_title_is_generic(self) -> None:
        result = attribute_eastmoney_article(
            article("国产算力产业迎来新进展", "寒武纪表示新一代人工智能芯片已经进入客户验证阶段。"),
            [self.cambricon, self.catl],
        )
        self.assertEqual(result["company"], "寒武纪")

    def test_eastmoney_quote_link_can_supply_a_missing_company(self) -> None:
        body = '<a href="https://quote.eastmoney.com/sz688256.html">行情</a>'
        result = attribute_eastmoney_article(
            article("国产AI芯片公司公布最新进展"),
            [self.cambricon, self.catl],
            page_body=body,
        )
        self.assertEqual(result["company"], "寒武纪")

    def test_unified_quote_link_is_supported(self) -> None:
        body = '<a href="https://quote.eastmoney.com/unify/r/105.IONQ">IonQ</a>'
        self.assertIn("IONQ", extract_eastmoney_linked_tickers(body))
        result = attribute_eastmoney_article(
            article("量子计算公司发布系统更新"),
            [self.ionq],
            page_body=body,
        )
        self.assertEqual(result["company"], "IonQ")

    def test_multi_stock_quote_page_is_not_assigned_to_one_company(self) -> None:
        body = (
            '<a href="https://quote.eastmoney.com/sz688256.html">寒武纪</a>'
            '<a href="https://quote.eastmoney.com/sz300750.html">宁德时代</a>'
        )
        result = attribute_eastmoney_article(
            article("芯片产业板块出现新变化", "多家公司受到关注。"),
            [self.cambricon, self.catl],
            page_body=body,
        )
        self.assertEqual(result["company"], "科技产业")
        self.assertNotIn("ticker", result)

    def test_bare_numeric_value_does_not_match_a_stock_code(self) -> None:
        result = attribute_eastmoney_article(
            article("项目投资金额继续增长", "项目编号688256，拟投资金额约50亿元。"),
            [self.cambricon],
        )
        self.assertEqual(result["company"], "科技产业")


if __name__ == "__main__":
    unittest.main()
