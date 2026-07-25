from __future__ import annotations

import unittest

from tools import wechat_snapshot_quality as quality


class WeChatSnapshotQualityTest(unittest.TestCase):
    def test_filters_technical_phrases_from_people(self) -> None:
        values = [
            "Joshua Achiam",
            "Noam Brown",
            "黄佳诺",
            "Claude Code",
            "Speculative Decoding",
            "EPIC Lab",
            "Mission Alignment",
            "Anthropic CEO",
            "论文链接",
            "OpenAI",
        ]
        cleaned = quality.clean_people(values, ["OpenAI", "Anthropic"])
        self.assertEqual(cleaned, ["Joshua Achiam", "Noam Brown", "黄佳诺"])

    def test_known_company_ownership_resolves_duplicate_article_to_ai(self) -> None:
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
            "title": "大三本科生一作，DeepSeek引用投机解码新研究",
            "summary": "DeepSeek引用新的推理模型研究。",
            "company": "DeepSeek",
            "mentionedCompanies": ["DeepSeek"],
            "mentionedPeople": ["Jianuo Huang", "Speculative Decoding"],
            "matchedTrackingTerms": ["推理模型"],
            "source": {"url": "https://mp.weixin.qq.com/s?mid=1&idx=1"},
        }
        articles = [
            {**shared, "id": "ai", "sector": "AI / AGI", "sourceId": "wechat-ai"},
            {**shared, "id": "robot", "sector": "机器人", "sourceId": "wechat-robot"},
        ]
        result = quality.resolve_cross_sector_articles(articles, tracking)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sector"], "AI / AGI")
        self.assertEqual(result[0]["mentionedPeople"], ["Jianuo Huang"])

    def test_title_terms_resolve_generic_company_article_to_robotics(self) -> None:
        tracking = {
            "tracks": [
                {
                    "name": "AI / AGI",
                    "enabled": True,
                    "keywords": ["推理模型", "大模型"],
                    "sampleCompanies": ["OpenAI"],
                },
                {
                    "name": "机器人",
                    "enabled": True,
                    "keywords": ["VLA", "具身智能", "机器人"],
                    "sampleCompanies": ["Figure AI"],
                },
            ]
        }
        shared = {
            "title": "60000小时炼出新开源VLA，20多种机器人都能用",
            "summary": "具身智能模型支持多种机器人。",
            "company": "科技产业",
            "mentionedCompanies": [],
            "mentionedPeople": [],
            "source": {"url": "https://mp.weixin.qq.com/s?mid=2&idx=1"},
        }
        articles = [
            {**shared, "id": "ai", "sector": "AI / AGI", "matchedTrackingTerms": []},
            {
                **shared,
                "id": "robot",
                "sector": "机器人",
                "matchedTrackingTerms": ["VLA", "机器人", "具身智能"],
            },
        ]
        result = quality.resolve_cross_sector_articles(articles, tracking)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["sector"], "机器人")


if __name__ == "__main__":
    unittest.main()
