from __future__ import annotations

import unittest

from tools import wechat_source_registry as registry


class WeChatSourceRegistryTest(unittest.TestCase):
    def test_configured_account_is_bound_to_matching_sector(self) -> None:
        tracks = [
            {
                "slug": "semiconductor",
                "name": "半导体",
                "keywords": ["HBM", "先进封装"],
                "people": ["黄仁勋"],
                "sampleCompanies": ["英伟达", "中芯国际"],
            }
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        names = {source["name"] for source in sources}
        self.assertIn("半导体行业观察", names)
        self.assertIn("集微网", names)
        for source in sources:
            self.assertEqual(source["sector"], "半导体")
            self.assertEqual(source["adapter"], "wechat_search")
            self.assertTrue(source.get("expectedAccounts"))
            self.assertIn("mp.weixin.qq.com", source["url"])
            self.assertIn("中芯国际", source["trackedCompanies"])

    def test_unconfigured_track_keeps_generic_discovery(self) -> None:
        tracks = [
            {
                "slug": "space",
                "name": "商业航天",
                "keywords": ["可复用火箭"],
                "people": ["埃隆·马斯克 @elonmusk"],
                "sampleCompanies": ["SpaceX"],
            }
        ]
        sources = registry.generated_wechat_sources(tracks, object())
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0]["name"], "微信公众号 · 商业航天")
        self.assertNotIn("expectedAccounts", sources[0])
        self.assertIn("SpaceX", sources[0]["trackedCompanies"])

    def test_account_name_must_match_whitelist(self) -> None:
        spec = {"expectedAccounts": ["量子位", "qbitai"]}
        self.assertTrue(registry.account_matches(spec, "量子位"))
        self.assertTrue(registry.account_matches(spec, "量子位Pro"))
        self.assertFalse(registry.account_matches(spec, "无关科技媒体"))
        self.assertFalse(registry.account_matches(spec, ""))


if __name__ == "__main__":
    unittest.main()
