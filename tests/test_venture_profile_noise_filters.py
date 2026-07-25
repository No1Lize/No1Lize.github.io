from __future__ import annotations

import unittest

from tools import venture_profile_extraction as extraction


class VentureProfileNoiseFilterTests(unittest.TestCase):
    def test_team_extraction_rejects_navigation_and_role_fragments(self) -> None:
        body = '''
        <html><head><title>领导团队</title></head><body>
          <p>关于智元 合伙人 新闻资讯 合伙人 无限生产力 合伙人</p>
          <p>联席 总裁 营销服 总裁</p>
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
        self.assertNotIn("联席", names)
        self.assertNotIn("营销服", names)

    def test_products_prioritize_catalog_and_reject_document_navigation(self) -> None:
        body = '''
        <html><head><title>产品中心</title></head><body>
          <h2>产品软件包</h2>
          <h2>产品参数</h2>
          <h2>产品手册</h2>
          <h2>产品资料与下载</h2>
          <h2>售后服务政策</h2>
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


if __name__ == "__main__":
    unittest.main()
