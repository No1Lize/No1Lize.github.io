from __future__ import annotations

import unittest

from tools import crawl_with_tracking as tracking
from tools import professional_media_sources as media


class ProfessionalMediaSourcesTest(unittest.TestCase):
    def test_registry_contains_100_unique_enabled_sources(self) -> None:
        payload = media.load_registry()
        sources = payload["sources"]
        self.assertEqual(len(sources), 100)
        self.assertEqual(len({source["id"] for source in sources}), 100)
        self.assertEqual(len({source["order"] for source in sources}), 100)
        self.assertTrue(all(source["enabled"] for source in sources))

        business_insider = next(
            source for source in sources if source["order"] == 23
        )
        self.assertEqual(business_insider["name"], "Business Insider Tech")
        self.assertEqual(business_insider["host"], "businessinsider.com")
        self.assertIn("Android Authority", business_insider["correctedFrom"])

    def test_grouped_specs_cover_every_source_exactly_once(self) -> None:
        tracks = tracking._enabled_tracks(tracking.load_tracking())
        specs = media.grouped_specs(tracks, tracking)
        covered = [
            row["id"]
            for spec in specs
            for row in spec.get("professionalMedia", [])
        ]
        expected = [source["id"] for source in media.enabled_sources()]
        self.assertEqual(set(covered), set(expected))
        self.assertEqual(len(covered), len(expected))
        self.assertTrue(specs)
        for spec in specs:
            self.assertLessEqual(len(spec["allowedHosts"]), 8)
            self.assertEqual(spec["adapter"], "rss")
            self.assertEqual(spec["sourceLevel"], "媒体报道")
            self.assertTrue(spec["url"].startswith("https://www.bing.com/search?"))

    def test_original_media_name_is_preserved(self) -> None:
        row = {
            "id": "techcrunch",
            "name": "TechCrunch",
            "url": "https://techcrunch.com/",
            "host": "techcrunch.com",
            "pathPrefix": "",
            "region": "美国",
            "focus": ["初创企业", "融资"],
        }
        article = {
            "id": "example",
            "sourceId": "professional-media-risk-01",
            "region": "全球",
            "source": {
                "name": "专业科技媒体 · 风险投资 · 01",
                "platform": "专业科技媒体",
                "url": "https://techcrunch.com/2026/07/26/example/",
                "level": "媒体报道",
            },
        }
        attributed = media.attribute_article(article, [row])
        self.assertIsNotNone(attributed)
        assert attributed is not None
        self.assertEqual(attributed["source"]["name"], "TechCrunch")
        self.assertEqual(attributed["source"]["platform"], "TechCrunch")
        self.assertEqual(attributed["professionalMediaId"], "techcrunch")
        self.assertEqual(attributed["region"], "美国")

    def test_section_scoped_source_rejects_other_site_sections(self) -> None:
        row = {
            "id": "the-startup",
            "name": "The Startup",
            "url": "https://medium.com/swlh",
            "host": "medium.com",
            "pathPrefix": "/swlh",
            "region": "全球",
            "focus": ["创业"],
        }
        self.assertIsNotNone(
            media.match_media("https://medium.com/swlh/example-story", [row])
        )
        self.assertIsNone(
            media.match_media("https://medium.com/another-publication/story", [row])
        )


if __name__ == "__main__":
    unittest.main()
