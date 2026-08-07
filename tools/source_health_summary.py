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
