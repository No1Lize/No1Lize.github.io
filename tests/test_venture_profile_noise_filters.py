from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import crawl_venture_profiles as crawler
from tools import venture_profile_extraction as extraction


class VentureProfileNoiseFilterTests(unittest.TestCase):
    def test_team_extraction_rejects_navigation_and_role_fragments(self) -> None:
        body = '''
        <html><head><title>领导团队</title></head><body>
          <p>关于智元 合伙人 新闻资讯 合伙人 无限生产力 合伙人</p>
          <p>智元 合伙人 联席 总裁 营销服 总裁 高级副 总裁</p>
          <p>邓泰华 创始人 彭志辉 联合创始人 姜青松 合伙人</p>
        </body></html>
        '''
        page = extraction.parse_public_page(
            "https://www.zhiyuan-robot.com/company/leadership",
            body,
            "company",
        )
        team = extraction.extract_team([page], ("智元机器人", "智元"))
        names = {item["name"] for item in team}
        self.assertEqual(names, {"邓泰华", "彭志辉", "姜青松"})
        self.assertNotIn("关于智元", names)
        self.assertNotIn("新闻资讯", names)
        self.assertNotIn("无限生产力", names)
        self.assertNotIn("智元", names)
        self.assertNotIn("联席", names)
        self.assertNotIn("营销服", names)
        self.assertNotIn("高级副", names)

    def test_products_prioritize_catalog_and_reject_document_navigation(self) -> None:
        body = '''
        <html><head><title>产品中心</title></head><body>
          <h2>产品软件包</h2>
          <h2>产品参数</h2>
          <h2>产品手册</h2>
          <h2>产品资料与下载</h2>
          <h2>售后服务政策</h2>
          <h2>具身智能服务机器人大赛</h2>
          <h2>Transforming Defense Capabilities with Advanced Technology</h2>
          <h2>远征A3人形机器人</h2>
          <a href="/products/a3">远征A3人形机器人</a>
        </body></html>
        '''
        page = extraction.parse_public_page(
            "https://www.zhiyuan-robot.com/products",
            body,
            "company",
        )
        products = extraction.extract_products(
            [page],
            "远征A2、灵犀X2 与 Genie Studio具身智能开发平台",
        )
        self.assertTrue(
            {"远征A2", "灵犀X2", "Genie Studio具身智能开发平台"}.issubset(
                set(products[:3])
            )
        )
        self.assertIn("远征A3人形机器人", products)
        self.assertNotIn("产品软件包", products)
        self.assertNotIn("产品参数", products)
        self.assertNotIn("产品手册", products)
        self.assertNotIn("产品资料与下载", products)
        self.assertNotIn("售后服务政策", products)
        self.assertNotIn("具身智能服务机器人大赛", products)
        self.assertNotIn("Transforming Defense Capabilities with Advanced Technology", products)

    def test_retained_history_is_resanitized_after_homepage_timeout(self) -> None:
        company = extraction.CatalogCompany(
            slug="agibot",
            name="智元机器人",
            english_name="AgiBot",
            region="中国",
            sector="机器人",
            stage="成长期",
            status="运营中",
            summary="研发具身智能机器人。",
            product="远征A2、灵犀X2",
            source_name="智元机器人",
            source_url="https://www.zhiyuan-robot.com/",
        )
        previous = {
            "slug": "agibot",
            "name": "智元机器人",
            "updatedAt": "2026-07-24T00:00:00+00:00",
            "status": "ok",
            "background": "完整背景。",
            "technology": "完整技术资料。",
            "products": ["产品手册", "具身智能服务机器人大赛", "远征A2"],
            "team": [
                {"name": "关于智元", "role": "合伙人", "summary": "", "sourceUrl": company.source_url},
                {"name": "智元", "role": "合伙人", "summary": "", "sourceUrl": company.source_url},
                {"name": "高级副", "role": "总裁", "summary": "", "sourceUrl": company.source_url},
                {"name": "邓泰华", "role": "创始人", "summary": "", "sourceUrl": company.source_url},
                {"name": "具身业务部", "role": "总裁", "summary": "", "sourceUrl": company.source_url},
            ],
            "financing": [],
            "capitalMarkets": [],
            "sources": [{"name": "智元机器人", "url": company.source_url, "level": "官方披露"}],
            "warnings": [],
            "evidenceScore": 90,
        }
        with patch.object(crawler, "crawl_pages", return_value=([], ["homepage timeout"])):
            profile, status = crawler.crawl_company(
                company,
                crawler.DEFAULT_USER_AGENT,
                6,
                previous,
            )
        self.assertEqual(status["status"], "retained")
        self.assertEqual([item["name"] for item in profile["team"]], ["邓泰华"])
        self.assertNotIn("产品手册", profile["products"])
        self.assertNotIn("具身智能服务机器人大赛", profile["products"])
        self.assertIn("远征A2", profile["products"])


if __name__ == "__main__":
    unittest.main()
