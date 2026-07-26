from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from tools import expand_tracking_entities as expander


def _fake_fetch(url: str) -> str:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    host = parsed.netloc

    if host.endswith("wikipedia.org") and query.get("action") == ["opensearch"]:
        term = query["search"][0]
        return json.dumps([term, [f"{term}条目"], [""], [""]])
    if host.endswith("wikipedia.org") and query.get("list") == ["search"]:
        return json.dumps(
            {
                "query": {
                    "search": [
                        {"title": "灵巧手"},
                        {"title": "宇树科技"},
                        {"title": "Figure AI"},
                    ]
                }
            }
        )
    if host == "suggestion.baidu.com":
        return 'window.baidu.sug({q:"seed",p:false,s:["人形机器人 灵巧手","人形机器人 触觉传感器"]});'
    if host == "suggestqueries.google.com":
        return json.dumps(["seed", ["embodied intelligence", "humanoid actuator"]])
    if host == "api.openalex.org":
        return json.dumps(
            {
                "results": [
                    {
                        "related_concepts": [
                            {"display_name": "Robot learning", "score": 0.7},
                            {"display_name": "noise", "score": 0.1},
                        ]
                    }
                ]
            }
        )
    if host == "www.wikidata.org" and query.get("action") == ["wbsearchentities"]:
        term = query["search"][0]
        if term == "宇树科技":
            return json.dumps({"search": [{"id": "Q100"}]})
        if term == "Figure AI":
            return json.dumps({"search": [{"id": "Q200"}]})
        return json.dumps({"search": []})
    if host == "www.wikidata.org" and query.get("action") == ["wbgetentities"]:
        entity = query["ids"][0]
        if entity == "Q100":
            claims = {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q4830453"}}
                        }
                    }
                ],
                "P856": [
                    {"mainsnak": {"datavalue": {"value": "https://www.unitree.com/"}}}
                ],
                "P17": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q148"}}}}
                ],
            }
            return json.dumps({"entities": {"Q100": {"claims": claims}}})
        if entity == "Q200":
            claims = {
                "P31": [
                    {
                        "mainsnak": {
                            "datavalue": {"value": {"id": "Q4830453"}}
                        }
                    }
                ],
                "P17": [
                    {"mainsnak": {"datavalue": {"value": {"id": "Q30"}}}}
                ],
            }
            return json.dumps({"entities": {"Q200": {"claims": claims}}})
    return ""


def _diverse_fetch(url: str) -> str:
    """Every seed resolves to its own unrelated morelike titles, so no
    candidate is ever confirmed by a second seed (score stays at 2.0)."""

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    host = parsed.netloc
    if host.endswith("wikipedia.org") and query.get("action") == ["opensearch"]:
        term = query["search"][0]
        return json.dumps([term, [f"{term}主题"], [""], [""]])
    if host.endswith("wikipedia.org") and query.get("list") == ["search"]:
        base = query["srsearch"][0].replace("morelike:", "")
        return json.dumps(
            {
                "query": {
                    "search": [
                        {"title": f"{base}关联技术甲"},
                        {"title": f"{base}关联技术乙"},
                    ]
                }
            }
        )
    if host == "www.wikidata.org" and query.get("action") == ["wbsearchentities"]:
        return json.dumps({"search": []})
    return ""


class ExpandTrackingEntitiesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.config_path = base / "user_tracking.json"
        self.ledger_path = base / "tracking_auto_discovery.json"
        self._original_config = expander.CONFIG_PATH
        self._original_ledger = expander.LEDGER_PATH
        expander.CONFIG_PATH = self.config_path
        expander.LEDGER_PATH = self.ledger_path

    def tearDown(self) -> None:
        expander.CONFIG_PATH = self._original_config
        expander.LEDGER_PATH = self._original_ledger
        self.tmp.cleanup()

    def _write_config(self, config: dict) -> None:
        self.config_path.write_text(
            json.dumps(config, ensure_ascii=False), encoding="utf-8"
        )

    def _read_config(self) -> dict:
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def _read_ledger(self) -> dict:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))

    def _base_config(self, **track_overrides) -> dict:
        track = {
            "slug": "robotics",
            "name": "人形机器人",
            "enabled": True,
            "custom": False,
            "keywords": ["人形机器人整机"],
            "people": [],
            "sampleCompanies": [],
        }
        track.update(track_overrides)
        return {
            "schemaVersion": 1,
            "tracks": [track],
            "listedCompanies": [],
            "sources": [],
        }

    def test_expands_keywords_companies_and_sources_from_public_web(self) -> None:
        self._write_config(self._base_config())
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)

        config = self._read_config()
        track = config["tracks"][0]
        self.assertIn("灵巧手", track["keywords"])
        self.assertIn("宇树科技", track["sampleCompanies"])
        sources = config["sources"]
        self.assertTrue(
            any(source["url"] == "https://www.unitree.com/" for source in sources)
        )
        auto_source = next(
            source for source in sources if source["url"] == "https://www.unitree.com/"
        )
        self.assertEqual(auto_source["region"], "中国")
        self.assertEqual(auto_source["sourceCategory"], "company")
        self.assertEqual(auto_source["sector"], "人形机器人")

        ledger = self._read_ledger()
        kinds = {(row["kind"], row["value"]) for row in ledger["added"]}
        self.assertIn(("keywords", "灵巧手"), kinds)
        self.assertIn(("sampleCompanies", "宇树科技"), kinds)
        self.assertIn(("sources", "https://www.unitree.com/"), kinds)

    def test_seeds_keywords_for_brand_new_track(self) -> None:
        self._write_config(
            self._base_config(slug="embodied", name="具身智能", custom=True, keywords=[])
        )
        rc = expander.run(["--seed-new-only"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertTrue(track["keywords"], "seeding must import keywords directly")
        # Seeding only fills the keyword area; other kinds stay untouched.
        self.assertEqual(track["people"], [])
        self.assertEqual(track["sampleCompanies"], [])

    def test_seed_new_only_skips_tracks_with_keywords(self) -> None:
        self._write_config(self._base_config())
        calls: list[str] = []

        def counting_fetch(url: str) -> str:
            calls.append(url)
            return _fake_fetch(url)

        rc = expander.run(["--seed-new-only"], fetch_text=counting_fetch)
        self.assertEqual(rc, 0)
        self.assertEqual(calls, [], "no network use when nothing needs seeding")
        self.assertEqual(self._read_config()["tracks"][0]["keywords"], ["人形机器人整机"])

    def test_removed_entries_become_tombstones_and_never_return(self) -> None:
        self._write_config(self._base_config())
        self.ledger_path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "updatedAt": "",
                    "tracks": {},
                    "added": [
                        {
                            "track": "robotics",
                            "kind": "keywords",
                            "value": "灵巧手",
                            "addedAt": "2026-07-01T00:00:00+00:00",
                            "evidence": ["wikipedia-morelike"],
                        }
                    ],
                    "removed": [],
                }
            ),
            encoding="utf-8",
        )
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        ledger = self._read_ledger()
        removed = {(row["kind"], row["value"]) for row in ledger["removed"]}
        self.assertIn(("keywords", "灵巧手"), removed)
        track = self._read_config()["tracks"][0]
        self.assertNotIn("灵巧手", track["keywords"])

    def test_diverse_seed_tracks_fall_back_to_relaxed_keywords(self) -> None:
        """Regression: tracks whose seeds share no related pages (GPU vs 先进
        封装 vs LPU) produced zero additions because no candidate was
        confirmed by two seeds; the relaxed pass must still surface a few
        keyword candidates instead of freezing the track."""

        self._write_config(
            self._base_config(
                slug="semiconductor",
                name="半导体",
                keywords=["GPU", "先进封装"],
            )
        )
        rc = expander.run(
            ["--only-track", "semiconductor"], fetch_text=_diverse_fetch
        )
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        added = [
            keyword for keyword in track["keywords"] if "关联技术" in keyword
        ]
        self.assertTrue(added, "relaxed pass must add single-source keywords")
        self.assertLessEqual(len(added), 3)

    def test_ignored_recommendations_block_candidates(self) -> None:
        self._write_config(
            self._base_config(
                ignoredRecommendations={"companies": ["宇树科技"], "keywords": []}
            )
        )
        rc = expander.run(["--only-track", "robotics"], fetch_text=_fake_fetch)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertNotIn("宇树科技", track["sampleCompanies"])

    def test_offline_run_changes_nothing(self) -> None:
        self._write_config(self._base_config())

        def offline(url: str) -> str:
            raise OSError("offline")

        rc = expander.run(["--only-track", "robotics"], fetch_text=offline)
        self.assertEqual(rc, 0)
        track = self._read_config()["tracks"][0]
        self.assertEqual(track["keywords"], ["人形机器人整机"])
        self.assertFalse(self.ledger_path.exists())

    def test_keyword_validation_rejects_generic_and_urls(self) -> None:
        self.assertEqual(expander.validate_keyword("人工智能"), "")
        self.assertEqual(expander.validate_keyword("https://example.com"), "")
        self.assertEqual(expander.validate_keyword("what is AND query"), "")
        self.assertEqual(expander.validate_keyword("灵巧手"), "灵巧手")
        self.assertEqual(expander.validate_keyword("  Robot   learning  "), "Robot learning")


if __name__ == "__main__":
    unittest.main()
