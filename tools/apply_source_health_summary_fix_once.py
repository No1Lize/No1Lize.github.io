from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if old not in text:
        raise RuntimeError(f"missing replacement anchor in {path}: {old[:100]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def replace_between(path: str, start: str, end: str, replacement: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    left = text.index(start)
    right = text.index(end, left)
    target.write_text(text[:left] + replacement + text[right:], encoding="utf-8")


def write(path: str, content: str) -> None:
    (ROOT / path).write_text(textwrap.dedent(content).lstrip("\n"), encoding="utf-8")


write(
    "tools/source_health_summary.py",
    r'''
    #!/usr/bin/env python3
    """Canonicalize source-health aggregate fields without changing source rows.

    This module is deliberately pure at the data-model level: it derives root
    summary counters/lists from the existing ``sources`` mapping and never
    advances failure/recovery streaks. It is safe to run after a git rebase or
    merge that may have combined source rows and stale aggregate fields.
    """

    from __future__ import annotations

    import argparse
    import json
    from copy import deepcopy
    from pathlib import Path
    from typing import Any, Callable

    ROOT = Path(__file__).resolve().parents[1]
    DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"


    def rebuild_source_health_summary(payload: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(payload)
        sources = result.get("sources") if isinstance(result.get("sources"), dict) else {}

        def ids_for(predicate: Callable[[dict[str, Any]], bool]) -> list[str]:
            return sorted(
                source_id
                for source_id, item in sources.items()
                if isinstance(item, dict) and predicate(item)
            )

        active = ids_for(lambda item: bool(item.get("alertActive")))
        quarantined = ids_for(lambda item: item.get("collectionState") == "quarantined")
        probation = ids_for(lambda item: item.get("collectionState") == "probation")
        low_priority = ids_for(lambda item: item.get("priority") == "low")
        performance_review = ids_for(
            lambda item: isinstance(item.get("performance"), dict)
            and bool(item["performance"].get("reviewRequired"))
        )
        downgrade = ids_for(
            lambda item: isinstance(item.get("performance"), dict)
            and item["performance"].get("reviewState") == "downgrade-candidate"
        )
        retirement = ids_for(
            lambda item: isinstance(item.get("performance"), dict)
            and item["performance"].get("reviewState") == "retire-candidate"
        )
        monitor = ids_for(
            lambda item: isinstance(item.get("performance"), dict)
            and item["performance"].get("reviewState") == "monitor"
        )
        result.update(
            {
                "sourceCount": len(sources),
                "activeAlertCount": len(active),
                "activeAlerts": active,
                "quarantinedSourceCount": len(quarantined),
                "quarantinedSources": quarantined,
                "probationSourceCount": len(probation),
                "probationSources": probation,
                "lowPrioritySourceCount": len(low_priority),
                "lowPrioritySources": low_priority,
                "performanceReviewSourceCount": len(performance_review),
                "performanceReviewSources": performance_review,
                "downgradeCandidateCount": len(downgrade),
                "downgradeCandidates": downgrade,
                "retirementCandidateCount": len(retirement),
                "retirementCandidates": retirement,
                "monitorSourceCount": len(monitor),
                "monitorSources": monitor,
                "sources": dict(sorted(sources.items())),
            }
        )
        return result


    def _read(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise SystemExit("source-health snapshot must be a JSON object")
        return value


    def main(argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--state", type=Path, default=DEFAULT_STATE_PATH)
        parser.add_argument("--check", action="store_true")
        args = parser.parse_args(argv)

        current = _read(args.state)
        normalized = rebuild_source_health_summary(current)
        changed = normalized != current
        print(json.dumps({"changed": changed, "sourceCount": normalized.get("sourceCount", 0)}, ensure_ascii=False))
        if args.check:
            if changed:
                raise SystemExit("source-health aggregate summary is not at a fixed point")
            return 0
        if changed:
            args.state.write_text(
                json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return 0


    if __name__ == "__main__":
        raise SystemExit(main())
    ''',
)

# tracking_source_governance delegates root summary normalization to the shared
# pure helper and exposes when the summary alone caused a fixed-point change.
replace_once(
    "tools/tracking_source_governance.py",
    "from urllib.parse import urlparse\n\n",
    '''from urllib.parse import urlparse\n\ntry:\n    from .source_health_summary import rebuild_source_health_summary\nexcept ImportError:\n    from source_health_summary import rebuild_source_health_summary\n\n''',
)
replace_between(
    "tools/tracking_source_governance.py",
    "def _rebuild_health_summary(payload: dict[str, Any]) -> dict[str, Any]:\n",
    "def normalize_tracking_sources(\n",
    '''def _rebuild_health_summary(payload: dict[str, Any]) -> dict[str, Any]:\n    return rebuild_source_health_summary(payload)\n\n\n''',
)
replace_once(
    "tools/tracking_source_governance.py",
    '''    health_removed = 0
    if health_sources:
''',
    '''    health_removed = 0
    health_summary_changed = False
    if health_sources:
''',
)
replace_once(
    "tools/tracking_source_governance.py",
    '''        next_health["sources"] = health_sources
        next_health = _rebuild_health_summary(next_health)
''',
    '''        next_health["sources"] = health_sources
        normalized_health = _rebuild_health_summary(next_health)
        health_summary_changed = normalized_health != next_health
        next_health = normalized_health
''',
)
replace_once(
    "tools/tracking_source_governance.py",
    '''        "healthRowsRemoved": health_removed,
        "removedSourceIds": sorted(removed_ids),
''',
    '''        "healthRowsRemoved": health_removed,
        "healthSummaryChanged": health_summary_changed,
        "removedSourceIds": sorted(removed_ids),
''',
)

# update_source_health uses the same final canonicalizer. This is intentionally
# after the stateful streak calculations; the helper changes root summaries only.
replace_once(
    "tools/update_source_health.py",
    '''    from source_quality_reviews import (
        DEFAULT_REVIEW_PATH,
        load_review_manifest,
        review_index,
    )

ROOT = Path(__file__).resolve().parents[1]
''',
    '''    from source_quality_reviews import (
        DEFAULT_REVIEW_PATH,
        load_review_manifest,
        review_index,
    )

try:
    from .source_health_summary import rebuild_source_health_summary
except ImportError:
    from source_health_summary import rebuild_source_health_summary

ROOT = Path(__file__).resolve().parents[1]
''',
)
replace_once(
    "tools/update_source_health.py",
    '''        "sources": dict(sorted(next_sources.items())),
    }
    summary = {
''',
    '''        "sources": dict(sorted(next_sources.items())),
    }
    result = rebuild_source_health_summary(result)
    summary = {
''',
)

write(
    "tests/test_source_health_summary.py",
    r'''
    from __future__ import annotations

    import copy
    import unittest

    from tools.source_health_summary import rebuild_source_health_summary
    from tools.tracking_source_governance import normalize_tracking_sources


    class SourceHealthSummaryTests(unittest.TestCase):
        def stale_payload(self) -> dict:
            return {
                "schemaVersion": 3,
                "generatedAt": "2026-08-07T06:00:00+00:00",
                "activeAlertCount": 3,
                "activeAlerts": ["a", "b", "ghost"],
                "quarantinedSourceCount": 2,
                "quarantinedSources": ["a", "b"],
                "probationSourceCount": 0,
                "probationSources": [],
                "sources": {
                    "a": {
                        "id": "a",
                        "alertActive": True,
                        "collectionState": "quarantined",
                        "priority": "normal",
                    },
                    "b": {
                        "id": "b",
                        "alertActive": True,
                        "collectionState": "probation",
                        "priority": "low",
                        "performance": {"reviewRequired": True, "reviewState": "monitor"},
                    },
                },
            }

        def test_rebuild_changes_only_aggregate_fields(self) -> None:
            payload = self.stale_payload()
            before_sources = copy.deepcopy(payload["sources"])
            normalized = rebuild_source_health_summary(payload)
            self.assertEqual(normalized["sources"], before_sources)
            self.assertEqual(normalized["activeAlertCount"], 2)
            self.assertEqual(normalized["activeAlerts"], ["a", "b"])
            self.assertEqual(normalized["quarantinedSources"], ["a"])
            self.assertEqual(normalized["probationSources"], ["b"])
            self.assertEqual(normalized["lowPrioritySources"], ["b"])
            self.assertEqual(normalized["performanceReviewSources"], ["b"])
            self.assertEqual(normalized["monitorSources"], ["b"])
            self.assertEqual(normalized["generatedAt"], payload["generatedAt"])

        def test_rebuild_is_idempotent(self) -> None:
            first = rebuild_source_health_summary(self.stale_payload())
            second = rebuild_source_health_summary(first)
            self.assertEqual(first, second)

        def test_governance_reports_summary_only_fixed_point_drift(self) -> None:
            config = {"tracks": [], "sources": []}
            ledger = {"added": [], "removed": []}
            payload = self.stale_payload()
            # Use non-auto health rows so governance has no row deletion reason.
            _, _, normalized, stats = normalize_tracking_sources(config, ledger, payload)
            self.assertEqual(normalized["sources"], payload["sources"])
            self.assertTrue(stats["healthSummaryChanged"])
            self.assertEqual(stats["healthRowsRemoved"], 0)


    if __name__ == "__main__":
        unittest.main()
    ''',
)

# Make the existing source-health tests enforce that normal state production is
# already canonical under the shared pure helper.
replace_once(
    "tests/test_source_health.py",
    "from tools.update_source_health import ",
    "from tools.source_health_summary import rebuild_source_health_summary\nfrom tools.update_source_health import ",
)

print("source-health summary fixed-point patch applied")
