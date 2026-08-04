#!/usr/bin/env python3
"""Temporary repository migration for the tracking-source governance rollout."""

from __future__ import annotations

from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"{path}: replacement point not found: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_governance() -> None:
    path = "tools/tracking_source_governance.py"
    replace_once(
        path,
        'FEED_SUBDOMAIN_PREFIXES = {\n    "www",',
        '''PUBLISHER_ROOT_DOMAINS = {
    # Slashdot exposes topic-specific hosts that are one publisher and one
    # discovery source for a given track. Keep this explicit rather than
    # broadly collapsing every news.* or tech.* subdomain on the web.
    "slashdot.org",
}
FEED_SUBDOMAIN_PREFIXES = {
    "www",''',
    )
    replace_once(
        path,
        '''    host = (parsed.hostname or "").strip(".").casefold()
    labels = [label for label in host.split(".") if label]
    while len(labels) > 2 and labels[0] in FEED_SUBDOMAIN_PREFIXES:
        labels.pop(0)
    return ".".join(labels)''',
        '''    host = (parsed.hostname or "").strip(".").casefold()
    for root in PUBLISHER_ROOT_DOMAINS:
        if host == root or host.endswith(f".{root}"):
            return root
    labels = [label for label in host.split(".") if label]
    while len(labels) > 2 and labels[0] in FEED_SUBDOMAIN_PREFIXES:
        labels.pop(0)
    return ".".join(labels)''',
    )
    replace_once(
        path,
        '''def is_auto_source(source: dict[str, Any] | None) -> bool:
    return str((source or {}).get("id") or "").startswith(AUTO_SOURCE_PREFIX)''',
        '''def is_auto_source(source: dict[str, Any] | None) -> bool:
    return str((source or {}).get("id") or "").startswith(AUTO_SOURCE_PREFIX)


def runtime_source_id(config_source_id: Any) -> str:
    source_id = str(config_source_id or "").strip()
    return f"user-source-{source_id}" if source_id else ""


def config_source_id(runtime_id: Any) -> str:
    source_id = str(runtime_id or "").strip()
    if source_id.startswith("user-source-"):
        return source_id[len("user-source-") :]
    return source_id


def runtime_source_ids(config_source_id_value: Any) -> set[str]:
    source_id = str(config_source_id_value or "").strip()
    return {value for value in (source_id, runtime_source_id(source_id)) if value}


def is_runtime_auto_source_id(value: Any) -> bool:
    return config_source_id(value).startswith(AUTO_SOURCE_PREFIX)''',
    )
    replace_once(
        path,
        '''        source["_index"] = index
        source["_originalUrl"] = str(source.get("url") or "")''',
        '''        source["_index"] = index
        source["_originalName"] = str(source.get("name") or "")
        source["_originalUrl"] = str(source.get("url") or "")''',
    )
    replace_once(
        path,
        '''        if _health_entry_is_dead_auto_source(
            source,
            health_sources.get(str(source.get("id") or "")),
        ):''',
        '''        source_health = next(
            (
                health_sources.get(source_id)
                for source_id in runtime_source_ids(source.get("id"))
                if isinstance(health_sources.get(source_id), dict)
            ),
            None,
        )
        if _health_entry_is_dead_auto_source(source, source_health):''',
    )
    replace_once(
        path,
        '''    for rows in grouped.values():
        ranked = sorted(
            rows,
            key=lambda row: _source_score(row, int(row.get("_index") or 0)),
            reverse=True,
        )
        winner = ranked[0]
        keep_ids.add(int(winner.get("_index") or 0))
        for duplicate in ranked[1:]:
            duplicate["_removalReason"] = "canonical-duplicate"
            removed_sources.append(duplicate)
            duplicate_removed += 1
            if discovery_suffix_count(duplicate.get("name")) > 1:
                recursive_removed += 1''',
        '''    for rows in grouped.values():
        manual_rows = [row for row in rows if not is_auto_source(row)]
        if manual_rows:
            # Governance never removes owner-entered duplicates. It only
            # removes automatic rows colliding with an owner source.
            for manual in manual_rows:
                keep_ids.add(int(manual.get("_index") or 0))
            duplicates = [row for row in rows if is_auto_source(row)]
        else:
            ranked = sorted(
                rows,
                key=lambda row: _source_score(row, int(row.get("_index") or 0)),
                reverse=True,
            )
            winner = ranked[0]
            keep_ids.add(int(winner.get("_index") or 0))
            duplicates = ranked[1:]
        for duplicate in duplicates:
            duplicate["_removalReason"] = "canonical-duplicate"
            removed_sources.append(duplicate)
            duplicate_removed += 1
            if discovery_suffix_count(duplicate.get("_originalName")) > 1:
                recursive_removed += 1''',
    )
    replace_once(
        path,
        '''    removed_ids = {
        str(source.get("id") or "") for source in removed_sources if source.get("id")
    }
    health_removed = 0
    if health_sources:
        for source_id in list(health_sources):
            if source_id in removed_ids or (
                source_id.startswith(AUTO_SOURCE_PREFIX)
                and source_id not in configured_ids
            ):
                health_sources.pop(source_id, None)
                health_removed += 1''',
        '''    removed_config_ids = {
        str(source.get("id") or "") for source in removed_sources if source.get("id")
    }
    removed_ids = {
        source_id
        for config_id in removed_config_ids
        for source_id in runtime_source_ids(config_id)
    }
    health_removed = 0
    if health_sources:
        for source_id in list(health_sources):
            if source_id in removed_ids or (
                is_runtime_auto_source_id(source_id)
                and config_source_id(source_id) not in configured_ids
            ):
                health_sources.pop(source_id, None)
                health_removed += 1''',
    )
    replace_once(
        path,
        '''    seen: dict[tuple[str, str, str, str], str] = {}
    configured_ids: set[str] = set()''',
        '''    seen: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    configured_ids: set[str] = set()''',
    )
    replace_once(
        path,
        '''        previous = seen.get(key)
        if previous:
            errors.append(f"{source_id}: duplicates canonical source {previous}")
        else:
            seen[key] = source_id''',
        '''        previous = seen.get(key)
        if previous and (is_auto_source(source) or is_auto_source(previous)):
            errors.append(
                f"{source_id}: duplicates canonical source {previous.get('id', '')}"
            )
        elif previous is None:
            seen[key] = source''',
    )
    replace_once(
        path,
        '''        for source_id in health_sources:
            if source_id.startswith(AUTO_SOURCE_PREFIX) and source_id not in configured_ids:
                errors.append(f"{source_id}: stale automatic source-health row")''',
        '''        for source_id in health_sources:
            if (
                is_runtime_auto_source_id(source_id)
                and config_source_id(source_id) not in configured_ids
            ):
                errors.append(f"{source_id}: stale automatic source-health row")''',
    )


def patch_governance_tests() -> None:
    path = Path("tests/test_tracking_source_governance.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '"source-auto-media-dead": {\n                    "collectionState": "quarantined",',
        '"user-source-source-auto-media-dead": {\n                    "collectionState": "quarantined",',
        1,
    )
    text = text.replace(
        '"source-auto-media-productive": {\n                    "collectionState": "quarantined",',
        '"user-source-source-auto-media-productive": {\n                    "collectionState": "quarantined",',
        1,
    )
    text = text.replace(
        'self.assertNotIn("source-auto-media-dead", next_health["sources"])',
        '''self.assertNotIn(
            "user-source-source-auto-media-dead",
            next_health["sources"],
        )''',
        1,
    )
    text = text.replace(
        '"source-auto-media-old": {\n                    "alertActive": True,',
        '"user-source-source-auto-media-old": {\n                    "alertActive": True,',
        1,
    )
    text = text.replace(
        'self.assertNotIn("source-auto-media-old", next_health["sources"])',
        '''self.assertNotIn(
            "user-source-source-auto-media-old",
            next_health["sources"],
        )''',
        1,
    )
    method = '''    def test_manual_duplicates_are_preserved(self):
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

'''
    marker = '\n\nif __name__ == "__main__":\n'
    if marker not in text:
        raise SystemExit("governance test insertion point not found")
    if "test_manual_duplicates_are_preserved" not in text:
        text = text.replace(marker, "\n\n" + method + 'if __name__ == "__main__":\n', 1)
    path.write_text(text, encoding="utf-8")


def patch_expansion() -> None:
    path = Path("tools/expand_tracking_entities.py")
    text = path.read_text(encoding="utf-8")
    import_point = "from urllib.request import Request, urlopen\n\nROOT = Path(__file__).resolve().parent.parent\n"
    import_block = '''from urllib.request import Request, urlopen

try:
    from .tracking_source_governance import (
        canonical_source_host,
        looks_like_derived_source_name,
        strip_discovery_source_suffix,
    )
except ImportError:
    from tracking_source_governance import (
        canonical_source_host,
        looks_like_derived_source_name,
        strip_discovery_source_suffix,
    )

ROOT = Path(__file__).resolve().parent.parent
'''
    if import_point not in text:
        raise SystemExit("expand import point not found")
    text = text.replace(import_point, import_block, 1)
    old = '''def source_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host'''
    if old not in text:
        raise SystemExit("source_host point not found")
    text = text.replace(old, '''def source_host(url: str) -> str:
    return canonical_source_host(url)''', 1)
    old = '''        source = article.get("source") or {}
        source_name = str(source.get("name") or source.get("platform") or "")
        host = source_host(str(source.get("url") or ""))
        region = str(article.get("region") or "全球")'''
    new = '''        source = article.get("source") or {}
        source_name = str(source.get("name") or source.get("platform") or "")
        source_id = str(source.get("id") or source.get("sourceId") or "")
        derived_source = (
            source_id.startswith("source-auto-")
            or source_id.startswith("user-source-source-auto-")
            or looks_like_derived_source_name(source_name)
        )
        host = source_host(str(source.get("url") or ""))
        region = str(article.get("region") or "全球")'''
    if old not in text:
        raise SystemExit("corpus source point not found")
    text = text.replace(old, new, 1)
    text = text.replace(
        '''            if host and host not in DENY_SOURCE_HOSTS:
                srow = row["sources"].setdefault(''',
        '''            if host and host not in DENY_SOURCE_HOSTS and not derived_source:
                srow = row["sources"].setdefault(''',
        1,
    )
    text = text.replace(
        '''        existing_hosts = {
            source_host(str(source.get("url") or ""))
            for source in config.get("sources", [])
        }''',
        '''        existing_hosts = {
            source_host(str(source.get("url") or ""))
            for source in config.get("sources", [])
            if normalize_term(str(source.get("sector") or ""))
            == normalize_term(str(track.get("name") or ""))
        }''',
        1,
    )
    text = text.replace(
        "            name = clean_candidate(top_names[0][0]) if top_names else host",
        '''            name = strip_discovery_source_suffix(
                clean_candidate(top_names[0][0]) if top_names else host
            )''',
        1,
    )
    text = text.replace(
        '                    "id": f"source-auto-media-{slugify(host)}",',
        '''                    "id": (
                        f"source-auto-media-{slugify(host)}-"
                        f"{slugify(str(track.get('slug') or track.get('name') or 'track'))}"
                    ),''',
        1,
    )
    text = text.replace(
        '                "evidence": ["wikidata-official-site"],',
        '''                "evidence": [
                    "corpus-proven-publisher"
                    if str(source.get("sourceCategory") or "") == "media"
                    else "wikidata-official-site"
                ],''',
        1,
    )
    path.write_text(text, encoding="utf-8")


def patch_source_health() -> None:
    path = Path("tools/update_source_health.py")
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        '''DEFAULT_POLICY_PATH = ROOT / "config" / "source_health_policy.json"
DEFAULT_SUMMARY_PATH = Path("/tmp/source-health-issue.md")''',
        '''DEFAULT_POLICY_PATH = ROOT / "config" / "source_health_policy.json"
DEFAULT_TRACKING_CONFIG_PATH = ROOT / "config" / "user_tracking.json"
DEFAULT_SUMMARY_PATH = Path("/tmp/source-health-issue.md")''',
        1,
    )
    text = text.replace(
        '''    manual_reviews: dict[str, dict[str, Any]] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:''',
        '''    manual_reviews: dict[str, dict[str, Any]] | None = None,
    configured_source_ids: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:''',
        1,
    )
    helper = '''

def _configured_source_present(
    runtime_id: str,
    configured_source_ids: set[str] | None,
) -> bool:
    if configured_source_ids is None:
        return True
    config_id = (
        runtime_id[len("user-source-") :]
        if runtime_id.startswith("user-source-")
        else runtime_id
    )
    return (
        not config_id.startswith("source-auto-")
        or config_id in configured_source_ids
    )
'''
    marker = "\n\ndef _parse_time(value: Any) -> datetime | None:\n"
    if marker not in text:
        raise SystemExit("source health helper point not found")
    text = text.replace(marker, helper + marker, 1)
    text = text.replace(
        '''        source_id = _source_id(raw_status)
        if not source_id:
            continue
        seen_ids.add(source_id)''',
        '''        source_id = _source_id(raw_status)
        if not source_id:
            continue
        if not _configured_source_present(source_id, configured_source_ids):
            continue
        seen_ids.add(source_id)''',
        1,
    )
    text = text.replace(
        '''    for source_id, raw_previous in previous_sources.items():
        if source_id in seen_ids or not isinstance(raw_previous, dict):
            continue''',
        '''    for source_id, raw_previous in previous_sources.items():
        if source_id in seen_ids or not isinstance(raw_previous, dict):
            continue
        if not _configured_source_present(source_id, configured_source_ids):
            continue''',
        1,
    )
    text = text.replace(
        '''    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)''',
        '''    parser.add_argument("--reviews", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument(
        "--tracking-config",
        type=Path,
        default=DEFAULT_TRACKING_CONFIG_PATH,
    )
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY_PATH)''',
        1,
    )
    text = text.replace(
        '''    manual_reviews = review_index(load_review_manifest(args.reviews))

    state, summary = update_health(
        previous_payload,
        article_payload,
        policy,
        manual_reviews=manual_reviews,
    )''',
        '''    manual_reviews = review_index(load_review_manifest(args.reviews))
    tracking_payload = _read_json(args.tracking_config, {})
    configured_source_ids = {
        str(source.get("id") or "")
        for source in tracking_payload.get("sources", [])
        if isinstance(source, dict)
        and str(source.get("id") or "").startswith("source-auto-")
    }

    state, summary = update_health(
        previous_payload,
        article_payload,
        policy,
        manual_reviews=manual_reviews,
        configured_source_ids=configured_source_ids,
    )''',
        1,
    )
    path.write_text(text, encoding="utf-8")

    test_path = Path("tests/test_source_health.py")
    tests = test_path.read_text(encoding="utf-8")
    method = '''    def test_removed_auto_runtime_source_is_not_preserved(self) -> None:
        previous = {
            "sources": {
                "user-source-source-auto-media-retired": {
                    "id": "user-source-source-auto-media-retired",
                    "collectionState": "quarantined",
                    "alertActive": True,
                },
                "owner-source": {
                    "id": "owner-source",
                    "collectionState": "quarantined",
                    "alertActive": True,
                },
            }
        }
        article_payload = {
            "sourceStatus": [
                {
                    "id": "user-source-source-auto-media-retired",
                    "status": "error",
                    "error": "HTTP 403",
                }
            ],
            "articles": [],
        }
        state, _ = update_health(
            previous,
            article_payload,
            DEFAULT_POLICY,
            now=datetime(2026, 8, 4, tzinfo=UTC),
            configured_source_ids=set(),
        )
        self.assertNotIn(
            "user-source-source-auto-media-retired",
            state["sources"],
        )
        self.assertIn("owner-source", state["sources"])
        self.assertTrue(state["sources"]["owner-source"]["missingFromCurrentRun"])

'''
    marker = '\n\nif __name__ == "__main__":\n'
    if marker not in tests:
        raise SystemExit("source health test point not found")
    if "test_removed_auto_runtime_source_is_not_preserved" not in tests:
        tests = tests.replace(marker, "\n\n" + method + 'if __name__ == "__main__":\n', 1)
    test_path.write_text(tests, encoding="utf-8")


def main() -> int:
    patch_governance()
    patch_governance_tests()
    patch_expansion()
    patch_source_health()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
