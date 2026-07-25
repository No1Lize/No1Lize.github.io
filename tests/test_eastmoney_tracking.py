import tempfile
import unittest
from pathlib import Path

from tools.crawl_official_with_tracking import (
    _eastmoney_summary,
    _is_probable_non_article,
)
from tools.eastmoney_entities import (
    attribute_eastmoney_article,
    build_listed_entity_index,
    is_eastmoney_article_url,
)


DETAIL_URL = "https://finance.eastmoney.com/a/202607233818911476.html"


def eastmoney_article(title: str) -> dict:
    return {
        "title": title,
        "summary": "文章介绍最新业务与产业进展。",
        "company": "东方财富",
        "sector": "AI / AGI",
        "region": "全球",
        "source": {
            "name": "东方财富",
            "url": DETAIL_URL,
            "level": "待交叉验证",
            "platform": "官方网站",
        },
    }


class EastmoneyTrackingTests(unittest.TestCase):
    def test_only_concrete_eastmoney_detail_urls_are_accepted(self) -> None:
        self.assertTrue(is_eastmoney_article_url(DETAIL_URL))
        self.assertFalse(
            is_eastmoney_article_url("https://fund.eastmoney.com/a/cjjyw.html")
        )
        self.assertFalse(is_eastmoney_article_url("https://www.eastmoney.com/"))

    def test_body_summary_prefers_article_paragraphs_and_drops_boilerplate(self) -> None:
        body = """
        <html><body>
          <div id="ContentBody">
            <p>寒武纪公布新一代人工智能芯片进展，重点提升大模型推理效率与能效。</p>
            <p>公司表示相关产品已经进入客户验证阶段，后续将继续扩大软硬件生态合作。</p>
            <p>免责声明：本文不构成任何投资建议。</p>
          </div>
        </body></html>
        """
        summary = _eastmoney_summary(body)
        self.assertIn("寒武纪公布新一代人工智能芯片进展", summary)
        self.assertIn("进入客户验证阶段", summary)
        self.assertNotIn("投资建议", summary)

    def test_channel_pages_are_rejected(self) -> None:
        article = eastmoney_article("基金要闻_天天基金网_东方财富网")
        article["source"]["url"] = "https://fund.eastmoney.com/a/cjjyw.html"
        self.assertTrue(_is_probable_non_article(article))

    def test_unique_company_name_match_sets_company_ticker_market_and_sector(self) -> None:
        entities = [
            {
                "id": "catalog-cambricon",
                "name": "寒武纪",
                "englishName": "",
                "ticker": "688256",
                "market": "A股",
                "sector": "半导体",
                "catalogSlug": "cambricon",
            }
        ]
        result = attribute_eastmoney_article(
            eastmoney_article("寒武纪发布新一代AI芯片，推理性能进一步提升"),
            entities,
        )
        self.assertEqual(result["company"], "寒武纪")
        self.assertEqual(result["ticker"], "688256")
        self.assertEqual(result["market"], "A股")
        self.assertEqual(result["sector"], "半导体")
        self.assertEqual(result["companySlug"], "cambricon")
        self.assertEqual(result["source"]["name"], "东方财富")

    def test_explicit_ticker_match_is_supported(self) -> None:
        entities = [
            {
                "id": "catalog-ionq",
                "name": "IonQ",
                "englishName": "",
                "ticker": "IONQ",
                "market": "美股",
                "sector": "量子计算",
                "catalogSlug": "ionq",
            }
        ]
        result = attribute_eastmoney_article(
            eastmoney_article("NYSE: IONQ 发布量子计算系统更新"),
            entities,
        )
        self.assertEqual(result["company"], "IonQ")
        self.assertEqual(result["region"], "美国")
        self.assertEqual(result["sector"], "量子计算")

    def test_multiple_company_matches_are_not_forced_to_one_entity(self) -> None:
        entities = [
            {
                "id": "catalog-cambricon",
                "name": "寒武纪",
                "englishName": "",
                "ticker": "688256",
                "market": "A股",
                "sector": "半导体",
                "catalogSlug": "cambricon",
            },
            {
                "id": "catalog-catl",
                "name": "宁德时代",
                "englishName": "",
                "ticker": "300750",
                "market": "A股",
                "sector": "新能源",
                "catalogSlug": "catl",
            },
        ]
        result = attribute_eastmoney_article(
            eastmoney_article("寒武纪与宁德时代领涨科技板块"),
            entities,
        )
        self.assertEqual(result["company"], "科技产业")
        self.assertNotIn("companySlug", result)
        self.assertNotIn("ticker", result)

    def test_tracking_watchlist_overrides_catalog_and_disabled_items_are_ignored(self) -> None:
        catalog = """
export const companies: Company[] = [
  { slug:"cambricon", name:"寒武纪", region:"中国", sector:"半导体", stage:"已上市", status:"已上市", summary:"", product:"", source:{} as any, confidence:1 },
];
export const ipoCompanies: IpoCompany[] = [
  { slug:"cambricon", name:"寒武纪", market:"A股", ticker:"688256", sector:"半导体", status:"已上市", latest:"", source:{} as any },
];
"""
        tracking = {
            "listedCompanies": [
                {
                    "id": "custom-active",
                    "name": "测试科技",
                    "ticker": "123456",
                    "market": "A股",
                    "sector": "智能制造",
                    "enabled": True,
                    "custom": True,
                },
                {
                    "id": "custom-disabled",
                    "name": "停用公司",
                    "ticker": "654321",
                    "market": "A股",
                    "sector": "半导体",
                    "enabled": False,
                    "custom": True,
                },
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog-data.ts"
            path.write_text(catalog, encoding="utf-8")
            entities = build_listed_entity_index(tracking, path)
        self.assertEqual([entity["name"] for entity in entities], ["测试科技"])


if __name__ == "__main__":
    unittest.main()
