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
        self.cambricon = entity(
            "寒武纪", "688256", "半导体", "cambricon"
        )
        self.catl = entity("宁德时代", "300750", "新能源", "catl")
        self.ionq = entity(
            "IonQ", "IONQ", "量子计算", "ionq", market="美股"
        )

    def test_unique_summary_company_is_used_when_title_is_generic(self) -> None:
        result = attribute_eastmoney_article(
            article(
                "国产算力产业迎来新进展",
                "寒武纪表示新一代人工智能芯片已经进入客户验证阶段。",
            ),
            [self.cambricon, self.catl],
        )
        self.assertEqual(result["company"], "寒武纪")
        self.assertEqual(result["ticker"], "688256")
        self.assertEqual(result["sector"], "半导体")
        self.assertEqual(result["companySlug"], "cambricon")

    def test_eastmoney_quote_link_can_supply_a_missing_company(self) -> None:
        body = """
        <div id="ContentBody">
          <p>公司公布了最新业务进展。</p>
          <a href="https://quote.eastmoney.com/sz688256.html">行情</a>
        </div>
        """
        self.assertIn("688256", extract_eastmoney_linked_tickers(body))
        result = attribute_eastmoney_article(
            article("国产AI芯片公司公布最新进展", "项目进入验证阶段。"),
            [self.cambricon, self.catl],
            page_body=body,
        )
        self.assertEqual(result["company"], "寒武纪")
        self.assertEqual(result["ticker"], "688256")

    def test_unified_quote_link_is_supported(self) -> None:
        body = (
            '<a href="https://quote.eastmoney.com/unify/r/105.IONQ">'
            "IonQ 行情</a>"
        )
        self.assertIn("IONQ", extract_eastmoney_linked_tickers(body))
        result = attribute_eastmoney_article(
            article("量子计算公司发布系统更新", "系统性能继续提升。"),
            [self.ionq],
            page_body=body,
        )
        self.assertEqual(result["company"], "IonQ")
        self.assertEqual(result["region"], "美国")

    def test_bare_numeric_value_does_not_match_a_stock_code(self) -> None:
        result = attribute_eastmoney_article(
            article(
                "项目投资金额继续增长",
                "项目编号688256，拟投资金额约50亿元。",
            ),
            [self.cambricon],
        )
        self.assertEqual(result["company"], "科技产业")
        self.assertNotIn("ticker", result)

    def test_explicit_numeric_stock_code_still_matches(self) -> None:
        result = attribute_eastmoney_article(
            article(
                "公司公布最新经营数据",
                "证券代码：688256，公司持续投入人工智能芯片研发。",
            ),
            [self.cambricon],
        )
        self.assertEqual(result["company"], "寒武纪")
        self.assertEqual(result["ticker"], "688256")

    def test_multiple_summary_companies_remain_unassigned(self) -> None:
        result = attribute_eastmoney_article(
            article(
                "科技板块出现新变化",
                "寒武纪与宁德时代均公布了新的产业投资计划。",
            ),
            [self.cambricon, self.catl],
        )
        self.assertEqual(result["company"], "科技产业")
        self.assertNotIn("ticker", result)
        self.assertNotIn("companySlug", result)


if __name__ == "__main__":
    unittest.main()
