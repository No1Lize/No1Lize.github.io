import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refresh_people_profiles_with_video",
    ROOT / "tools" / "refresh_people_profiles_with_video.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


class PeopleVideoEnrichmentTest(unittest.TestCase):
    def setUp(self):
        self.candidate = {
            "slug": "sam-altman",
            "name": "Sam Altman",
            "englishName": "Sam Altman",
            "aliases": ["Sam Altman"],
            "handles": ["sama"],
            "sectors": ["AI / AGI"],
            "override": {
                "roleHint": "OpenAI 首席执行官",
                "organizationHints": ["OpenAI"],
                "productHints": ["ChatGPT"],
            },
        }

    def test_online_enrichment_adds_video_to_materials_and_speeches(self):
        video = {
            "title": "Sam Altman interview on AI",
            "date": "2026-07-25",
            "type": "interview",
            "url": "https://www.youtube.com/watch?v=abc1234",
            "source": "YouTube · Example Channel",
        }
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(MODULE, "discover_person_video_materials", return_value=[video]), patch.object(
            MODULE, "discover_person_wechat_video_materials", return_value=[]
        ):
            profile = MODULE.enrich_candidate(self.candidate, None, [], offline=False)
        self.assertIn(video["url"], [item["url"] for item in profile["materials"]])
        self.assertIn(video["url"], [item["url"] for item in profile["speeches"]])
        self.assertIn(video["url"], profile["sources"])

    def test_embedded_wechat_channel_material_is_merged(self):
        video = {
            "title": "Sam Altman 公开对话",
            "date": "2026-07-25",
            "type": "qa",
            "url": "https://channels.weixin.qq.com/web/pages/feed?oid=example",
            "source": "微信视频号 · 科技访谈",
        }
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(MODULE, "discover_person_video_materials", return_value=[]), patch.object(
            MODULE, "discover_person_wechat_video_materials", return_value=[video]
        ):
            profile = MODULE.enrich_candidate(self.candidate, None, [], offline=False)
        self.assertEqual(profile["speeches"][0]["url"], video["url"])
        self.assertIn(video["url"], profile["sources"])

    def test_offline_validation_never_calls_video_platforms(self):
        with patch.object(
            MODULE, "discover_person_video_materials", side_effect=AssertionError("network discovery must be skipped")
        ), patch.object(
            MODULE, "discover_person_wechat_video_materials", side_effect=AssertionError("article discovery must be skipped")
        ):
            profile = MODULE.enrich_candidate(self.candidate, None, [], offline=True)
        self.assertEqual(profile["materials"], [])

    def test_previous_video_is_retained_when_new_discovery_returns_nothing(self):
        previous = {
            "materials": [{
                "title": "Sam Altman 公开对话",
                "date": "2026-07-20",
                "type": "qa",
                "url": "https://www.bilibili.com/video/BV1existing",
                "source": "Bilibili",
            }],
            "summary": "",
            "background": "",
            "role": "",
            "organizations": [],
            "products": [],
            "works": [],
            "books": [],
            "concepts": [],
        }
        with patch.object(MODULE.core, "fetch_wikipedia", return_value=None), patch.object(
            MODULE.core, "fetch_wikidata", return_value=None
        ), patch.object(MODULE, "discover_person_video_materials", return_value=[]), patch.object(
            MODULE, "discover_person_wechat_video_materials", return_value=[]
        ):
            profile = MODULE.enrich_candidate(self.candidate, previous, [], offline=False)
        self.assertEqual(profile["materials"][0]["url"], previous["materials"][0]["url"])
        self.assertEqual(profile["speeches"][0]["url"], previous["materials"][0]["url"])


if __name__ == "__main__":
    unittest.main()
