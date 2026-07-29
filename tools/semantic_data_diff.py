#!/usr/bin/env python3
"""Detect meaningful JSON changes while ignoring refresh-only timestamps.

Git-backed snapshots should be committed when user-visible data or source health
changes, not merely because a crawler stamped a new attempt time.  The command
prints a JSON result and exits non-zero only for malformed inputs or Git errors.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

VOLATILE_KEYS = {
    "generatedAt",
    "updatedAt",
    "archivedAt",
    "lastAttemptAt",
    "completedAt",
    "trackingEnrichedAt",
    "refreshedAt",
    "checkedAt",
    "lastCheckedAt",
    "lastRunAt",
    "lastSeenAt",
    "lastSuccessAt",
    "lastFailureAt",
    "runId",
    "commit",
    # The complete audit describes this execution. Its underlying article,
    # source-status and health changes are compared separately.
    "refreshAudit",
}


def canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in VOLATILE_KEYS
        }
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    return value


def semantic_equal(previous: Any, current: Any) -> bool:
    return canonicalize(previous) == canonicalize(current)


def load_json_text(text: str, label: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {label}: {exc}") from exc


def read_git_json(base: str, path: str) -> Any | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{path}"],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        if "exists on disk, but not in" in result.stderr or "does not exist" in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or f"git show failed for {path}")
    return load_json_text(result.stdout, f"{base}:{path}")


def compare_paths(base: str, paths: list[str]) -> list[str]:
    changed: list[str] = []
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"missing working-tree snapshot: {raw_path}")
        current = load_json_text(path.read_text(encoding="utf-8"), raw_path)
        previous = read_git_json(base, raw_path)
        if previous is None or not semantic_equal(previous, current):
            changed.append(raw_path)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD")
    parser.add_argument("paths", nargs="+")
    args = parser.parse_args()

    changed = compare_paths(args.base, args.paths)
    print(
        json.dumps(
            {"changed": bool(changed), "paths": changed},
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
