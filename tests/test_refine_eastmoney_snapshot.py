from __future__ import annotations

import unittest

from tools.refine_eastmoney_snapshot import is_relevant_eastmoney_article


class EastmoneyMarketRoundupTests(unittest.TestCase):
    def test_overnight_market_selloff_is_not_intelligence_article(self) -> None:
        article = {
            "sourceId": "official-user-东方财富",
            "title": "凌晨全线大跌！特朗普重磅发声！美股半导体、存储、光通信集体重挫",
            "summary": "美股半导体指数大跌，多个板块承压，市场交易情绪下降。",
            "company": "科技产业",
            "source": {
                "name": "东方财富",
                "url": "https://finance.eastmoney.com/a/202607253820914018.html",
            },
        }

        relevant, reason = is_relevant_eastmoney_article(article, set())

        self.assertFalse(relevant)
        self.assertEqual(reason, "roundup")

    def test_single_company_loss_is_not_filtered_as_market_roundup(self) -> None:
        article = {
            "sourceId": "official-user-东方财富",
            "title": "某芯片公司股价下跌但仍推进先进封装研发",
            "summary": "公司公布先进封装技术进展。",
            "company": "科技产业",
            "source": {
                "name": "东方财富",
                "url": "https://finance.eastmoney.com/a/202607253820914019.html",
            },
        }

        relevant, reason = is_relevant_eastmoney_article(article, set())

        self.assertTrue(relevant)
        self.assertEqual(reason, "technology-title")


if __name__ == "__main__":
    unittest.main()
