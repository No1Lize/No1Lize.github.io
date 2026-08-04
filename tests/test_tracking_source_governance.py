import unittest

from tools import tracking_source_governance as governance


class TrackingSourceGovernanceTests(unittest.TestCase):
    def _config(self, sources):
        return {
            "tracks": [
                {"slug": "venture-capital", "name": "风险投资", "enabled": True},
                {"slug": "semiconductor", "name": "半导体", "enabled": True},
            ],
            "sources": sources,
        }

    def test_recursive_discovery_suffix_is_removed(self):
        self.assertEqual(
            governance.strip_discovery_source_suffix(
                "Slashdot · 风险投资信源 · 风险投资信源 · 风险投资信源"
            ),
            "Slashdot",
        )
        self.assertEqual(
            governance.discovery_suffix_count(
                "Slashdot · 风险投资信源 · 风险投资信源"
            ),
            2,
        )

    def test_feed_and_www_hosts_share_one_canonical_origin(self):
        self.assertEqual(
            governance.canonical_source_host(
                "https://feeds.slashdot.org/Slashdot/slashdotMain"
            ),
            "slashdot.org",
        )
        self.assertEqual(
            governance.canonical_source_host("https://www.slashdot.org/"),
            "slashdot.org",
        )
        self.assertEqual(
            governance.canonical_source_url("https://rss.slashdot.org/feed.xml"),
            "https://slashdot.org/",
        )

    def test_normalization_keeps_one_source_per_origin_and_track(self):
        config = self._config(
            [
                {
                    "id": "source-auto-media-slashdot-a",
                    "name": "Slashdot · 风险投资信源 · 风险投资信源",
                    "url": "https://feeds.slashdot.org/Slashdot/slashdotMain",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
                {
                    "id": "source-auto-media-slashdot-b",
                    "name": "Slashdot · 风险投资信源",
                    "url": "https://www.slashdot.org/",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
                {
                    "id": "source-auto-media-slashdot-semiconductor",
                    "name": "Slashdot · 半导体信源",
                    "url": "https://slashdot.org/topics/hardware",
                    "sourceCategory": "media",
                    "sector": "半导体",
                    "enabled": True,
                },
            ]
        )
        next_config, _, _, stats = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            {"sources": {}},
        )
        self.assertEqual(len(next_config["sources"]), 2)
        venture = next(
            source
            for source in next_config["sources"]
            if source["sector"] == "风险投资"
        )
        self.assertEqual(venture["name"], "Slashdot · 风险投资信源")
        self.assertEqual(venture["url"], "https://slashdot.org/")
        self.assertEqual(stats["duplicatesRemoved"], 1)
        self.assertEqual(governance.validate_tracking_sources(next_config), [])

    def test_owner_entered_source_wins_over_automatic_duplicate(self):
        config = self._config(
            [
                {
                    "id": "owner-slashdot",
                    "name": "Slashdot",
                    "url": "https://slashdot.org/",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
                {
                    "id": "source-auto-media-slashdot",
                    "name": "Slashdot · 风险投资信源",
                    "url": "https://feeds.slashdot.org/rss/slashdot.xml",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
            ]
        )
        next_config, _, _, stats = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            {"sources": {}},
        )
        self.assertEqual([source["id"] for source in next_config["sources"]], ["owner-slashdot"])
        self.assertEqual(stats["duplicatesRemoved"], 1)

    def test_never_productive_quarantined_auto_source_is_retired(self):
        config = self._config(
            [
                {
                    "id": "source-auto-media-dead",
                    "name": "Dead Media · 风险投资信源",
                    "url": "https://dead.example/",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
                {
                    "id": "source-auto-media-productive",
                    "name": "Useful Media · 风险投资信源",
                    "url": "https://useful.example/",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                },
            ]
        )
        health = {
            "sources": {
                "user-source-source-auto-media-dead": {
                    "collectionState": "quarantined",
                    "consecutiveFailures": 20,
                    "quarantineThreshold": 7,
                    "lastProductiveAt": None,
                    "alertActive": True,
                },
                "user-source-source-auto-media-productive": {
                    "collectionState": "quarantined",
                    "consecutiveFailures": 20,
                    "quarantineThreshold": 7,
                    "lastProductiveAt": "2026-08-01T00:00:00+00:00",
                    "alertActive": True,
                },
            }
        }
        next_config, _, next_health, stats = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            health,
        )
        self.assertEqual(
            [source["id"] for source in next_config["sources"]],
            ["source-auto-media-productive"],
        )
        self.assertNotIn(
            "user-source-source-auto-media-dead",
            next_health["sources"],
        )
        self.assertEqual(stats["deadAutoSourcesRemoved"], 1)
        self.assertEqual(stats["healthRowsRemoved"], 1)

    def test_ledger_rewrites_retained_url_without_tombstoning_it(self):
        config = self._config(
            [
                {
                    "id": "source-auto-media-slashdot",
                    "name": "Slashdot · 风险投资信源",
                    "url": "https://feeds.slashdot.org/rss.xml",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                    "enabled": True,
                }
            ]
        )
        ledger = {
            "added": [
                {
                    "track": "venture-capital",
                    "kind": "sources",
                    "value": "https://feeds.slashdot.org/rss.xml",
                }
            ],
            "removed": [],
        }
        _, next_ledger, _, stats = governance.normalize_tracking_sources(
            config,
            ledger,
            {"sources": {}},
        )
        self.assertEqual(
            next_ledger["added"][0]["value"],
            "https://slashdot.org/",
        )
        self.assertEqual(next_ledger["removed"], [])
        self.assertEqual(stats["ledgerValuesRewritten"], 1)

    def test_stale_auto_health_rows_are_removed(self):
        config = self._config([])
        health = {
            "sources": {
                "user-source-source-auto-media-old": {
                    "alertActive": True,
                    "collectionState": "quarantined",
                },
                "owner-source": {
                    "alertActive": True,
                    "collectionState": "quarantined",
                },
            }
        }
        _, _, next_health, stats = governance.normalize_tracking_sources(
            config,
            {"added": [], "removed": []},
            health,
        )
        self.assertNotIn(
            "user-source-source-auto-media-old",
            next_health["sources"],
        )
        self.assertIn("owner-source", next_health["sources"])
        self.assertEqual(next_health["activeAlertCount"], 1)
        self.assertEqual(stats["healthRowsRemoved"], 1)


    def test_manual_duplicates_are_preserved(self):
        config = self._config(
            [
                {
                    "id": "owner-a",
                    "name": "Owner A",
                    "url": "https://owner.example/",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                },
                {
                    "id": "owner-b",
                    "name": "Owner B",
                    "url": "https://www.owner.example/news",
                    "sourceCategory": "media",
                    "sector": "风险投资",
                },
            ]
        )
        next_config, _, _, stats = governance.normalize_tracking_sources(
            config, {"added": [], "removed": []}, {"sources": {}}
        )
        self.assertEqual(len(next_config["sources"]), 2)
        self.assertEqual(stats["duplicatesRemoved"], 0)
        self.assertEqual(governance.validate_tracking_sources(next_config), [])

    def test_runtime_source_identity_maps_to_config_source(self):
        self.assertEqual(
            governance.runtime_source_id("source-auto-media-example"),
            "user-source-source-auto-media-example",
        )
        self.assertEqual(
            governance.config_source_id("user-source-source-auto-media-example"),
            "source-auto-media-example",
        )
        self.assertTrue(
            governance.is_runtime_auto_source_id(
                "user-source-source-auto-media-example"
            )
        )

if __name__ == "__main__":
    unittest.main()
