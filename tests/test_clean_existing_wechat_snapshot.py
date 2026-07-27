from __future__ import annotations

import unittest

from tools import clean_existing_wechat_snapshot as cleanup


class CleanExistingWeChatSnapshotTest(unittest.TestCase):
    def test_cleans_people_and_keeps_best_sector_without_touching_other_sources(self) -> None:
        tracking = {
            "tracks": [
                {
                    "name": "AI / AGI",
                    "enabled": True,
                    "keywords": ["推理模型", "大模型", "DeepSeek"],
                    "sampleCompanies": ["DeepSeek", "OpenAI", "Anthropic"],
                },
                {
                    "name": "机器人",
                    "enabled": True,
                    "keywords": ["VLA", "具身智能", "机器人"],
                    "sampleCompanies": ["Figure AI", "宇树科技"],
                },
            ]
        }
        shared = {
            "title": "DeepSeek引用投机解码新研究",
            "summary": "DeepSeek引用新的推理模型研究。",
            "company": "DeepSeek",
            "mentionedCompanies": ["DeepSeek"],
            "mentionedPeople": ["Jianuo Huang", "Speculative Decoding"],
            "matchedTrackingTerms": ["推理模型"],
            "source": {
                "url": "https://mp.weixin.qq.com/s?mid=1&idx=1",
                "platform": "微信",
            },
            "wechatAccount": "量子位",
        }
        ordinary = {
            "id": "news",
            "sourceId": "news-source",
            "title": "普通新闻",
            "source": {"url": "https://example.com/news", "platform": "新闻"},
        }
        payload = {
            "schemaVersion": 3,
            "articles": [
                ordinary,
                {**shared, "id": "ai", "sourceId": "user-track-wechat-qbitai-ai", "sector": "AI / AGI"},
                {**shared, "id": "robot", "sourceId": "user-track-wechat-qbitai-robotics", "sector": "机器人"},
            ],
            "wechatIngestion": {},
        }
        result = cleanup.clean_snapshot(payload, tracking)
        self.assertEqual(result["articleCount"], 2)
        self.assertEqual(result["articles"][0]["id"], "news")
        wechat = result["articles"][1]
        self.assertEqual(wechat["sector"], "AI / AGI")
        self.assertEqual(wechat["mentionedPeople"], ["Jianuo Huang"])
        self.assertEqual(
            result["wechatIngestion"]["qualityRemovedCrossSectorDuplicates"],
            1,
        )
        self.assertEqual(result["wechatIngestion"]["qualityRemovedNonPeople"], 3)
        self.assertEqual(result["wechatIngestion"]["nonWechatArticlesPreserved"], 1)


if __name__ == "__main__":
    unittest.main()
