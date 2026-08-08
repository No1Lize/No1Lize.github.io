from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools import source_portfolio


class SourcePortfolioTests(unittest.TestCase):
    @staticmethod
    def specs(count: int = 100) -> list[dict]:
        return [
            {
                "id": f"professional-media-source-{index:03d}",
                "name": f"Source {index}",
                "url": f"https://www.bing.com/search?format=rss&q=source-{index}",
                "sourceUrl": f"https://source{index}.example/",
                "maxItems": 4,
                "directRequestBudget": {
                    "timeoutSeconds": 8,
                    "attempts": 1,
                    "feedLimit": 2,
                    "candidateLimit": 8,
                },
                "professionalMedia": [
                    {
                        "id": f"source-{index:03d}",
                        "name": f"Source {index}",
                        "url": f"https://source{index}.example/",
                        "host": f"source{index}.example",
                    }
                ],
            }
            for index in range(count)
        ]

    def test_catalog_keeps_all_sources_but_only_core_gets_corroboration_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "health.json"
            health.write_text("{}", encoding="utf-8")
            specs = source_portfolio.classify_professional_media_specs(
                self.specs(), health_path=health, core_limit=36
            )
        self.assertEqual(len(specs), 100)
        self.assertEqual(sum(spec["sourceRole"] == "corroboration" for spec in specs), 36)
        self.assertEqual(sum(spec["sourceRole"] == "discovery" for spec in specs), 64)
        tail = specs[-1]
        self.assertTrue(tail["discoveryOnly"])
        self.assertEqual(tail["maxItems"], 1)
        self.assertEqual(tail["directRequestBudget"]["feedLimit"], 0)
        self.assertEqual(tail["professionalMedia"][0]["sourceRole"], "discovery")

    def test_health_downgrade_overrides_core_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            health = Path(tmp) / "health.json"
            health.write_text(
                json.dumps({"downgradeCandidates": ["professional-media-source-000"]}),
                encoding="utf-8",
            )
            specs = source_portfolio.classify_professional_media_specs(
                self.specs(3), health_path=health, core_limit=3
            )
        self.assertEqual(specs[0]["sourceRole"], "discovery")
        self.assertEqual(specs[1]["sourceRole"], "corroboration")

    def test_discovery_media_uses_search_only_collection(self) -> None:
        class FakeModule:
            @staticmethod
            def attribute_article(article, rows):
                return dict(article)

            @staticmethod
            def match_media(_url, rows):
                return rows[0]

            @staticmethod
            def _dedupe_attributed(articles, rows, _crawler, limit):
                result = []
                for article in articles:
                    attributed = FakeModule.attribute_article(article, rows)
                    if attributed:
                        result.append(attributed)
                    if len(result) >= limit:
                        break
                return result

            @staticmethod
            def crawl_professional_source(*_args, **_kwargs):
                raise AssertionError("core crawler must not be used for discovery tier")

        class FakeCrawler:
            @staticmethod
            def _status(source_id, name, status, scanned, accepted, *, failed=0, platform="", error=None):
                result = {
                    "id": source_id,
                    "name": name,
                    "status": status,
                    "scanned": scanned,
                    "accepted": accepted,
                    "failed": failed,
                    "platform": platform,
                }
                if error:
                    result["error"] = error
                return result

        source_portfolio.install_professional_media(FakeModule)
        spec = self.specs(1)[0]
        spec["sourceRole"] = "discovery"
        spec["discoveryOnly"] = True
        spec["professionalMedia"][0]["sourceRole"] = "discovery"

        calls = []

        def primary(discovery_spec, _user_agent):
            calls.append(discovery_spec["adapter"])
            return [
                {
                    "id": "one",
                    "sourceId": spec["id"],
                    "source": {"url": "https://source0.example/story"},
                }
            ], {"scanned": 1, "failed": 0}

        articles, status = FakeModule.crawl_professional_source(
            spec, "agent", FakeCrawler(), object(), primary
        )
        self.assertEqual(calls, ["rss"])
        self.assertEqual(len(articles), 1)
        self.assertEqual(articles[0]["source"]["sourceRole"], "discovery")
        self.assertEqual(status["adapter"], "professional-media-v2-discovery")
        self.assertEqual(status["strategies"], ["public-search-rss"])


if __name__ == "__main__":
    unittest.main()
