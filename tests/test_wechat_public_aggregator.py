from __future__ import annotations

import unittest
from unittest.mock import patch

from tools import wechat_public_aggregator as aggregator


class WeChatPublicAggregatorTests(unittest.TestCase):
    def test_account_matched_direct_article_is_extracted(self) -> None:
        body = """
        <article>
          <a href="https://mp.weixin.qq.com/s/AbCdEf123">大模型推理效率取得新突破</a>
          <a href="https://mp.weixin.qq.com/s/AbCdEf123">打开原文</a>
          <div>AI 量子位 2026-07-22 05:00:00 UTC</div>
        </article>
        """
        rows = aggregator.parse_public_index(
            body,
            {
                "name": "量子位",
                "queryIdentity": "量子位",
                "expectedAccounts": ["量子位"],
                "maxItems": 2,
            },
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["account"], "量子位")
        self.assertEqual(rows[0]["publishedAt"], "2026-07-22")
        self.assertEqual(rows[0]["directUrl"], "https://mp.weixin.qq.com/s/AbCdEf123")

    def test_other_accounts_are_not_misattributed(self) -> None:
        body = """
        <a href="https://mp.weixin.qq.com/s/Other123">机器人行业动态</a>
        <div>AI 机器之心 2026-07-22 04:00:00 UTC</div>
        """
        rows = aggregator.parse_public_index(
            body,
            {
                "name": "量子位",
                "queryIdentity": "量子位",
                "expectedAccounts": ["量子位"],
            },
        )
        self.assertEqual(rows, [])

    def test_primary_direct_results_win_over_fallback(self) -> None:
        class Index:
            @staticmethod
            def discover(_spec):
                return ([{"directUrl": "https://mp.weixin.qq.com/s/primary"}], {"provider": "sogou-weixin"})

        index = Index()
        aggregator.install(index)
        with patch.object(aggregator, "discover") as fallback:
            rows, meta = index.discover({"name": "量子位"})
        self.assertEqual(meta["provider"], "sogou-weixin")
        self.assertEqual(rows[0]["directUrl"], "https://mp.weixin.qq.com/s/primary")
        fallback.assert_not_called()


if __name__ == "__main__":
    unittest.main()
