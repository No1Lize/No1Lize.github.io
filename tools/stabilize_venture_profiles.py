#!/usr/bin/env python3
"""Stabilize venture profiles across structural and entity-semantic gates.

The structural finalizer and entity-semantic gate enforce complementary
contracts. This terminal orchestrator alternates both deterministic transforms
until the snapshot is unchanged by either one, preventing publication when two
individually idempotent gates disagree on a derived field.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from .enforce_venture_entity_semantics import enforce_snapshot
    from .finalize_venture_profiles import CATALOG_PATH, SNAPSHOT_PATH, finalize_snapshot
except ImportError:
    from enforce_venture_entity_semantics import enforce_snapshot
    from finalize_venture_profiles import CATALOG_PATH, SNAPSHOT_PATH, finalize_snapshot


def stabilize_snapshot(
    payload: dict[str, Any], catalog_text: str, *, max_cycles: int = 6
) -> tuple[dict[str, Any], dict[str, Any]]:
    current = copy.deepcopy(payload)
    diagnostics: dict[str, Any] = {
        "cycles": 0,
        "structuralChangedCompanies": 0,
        "structuralChangedInstitutions": 0,
        "semanticChangedCompanies": 0,
        "semanticChangedInstitutions": 0,
    }

    for cycle in range(1, max_cycles + 1):
        finalized, structural = finalize_snapshot(current, catalog_text)
        enforced, semantic = enforce_snapshot(finalized, catalog_text)
        diagnostics["cycles"] = cycle
        diagnostics["structuralChangedCompanies"] += int(
            structural.get("changedCompanies", 0) or 0
        )
        diagnostics["structuralChangedInstitutions"] += int(
            structural.get("changedInstitutions", 0) or 0
        )
        diagnostics["semanticChangedCompanies"] += int(
            semantic.get("changedCompanies", 0) or 0
        )
        diagnostics["semanticChangedInstitutions"] += int(
            semantic.get("changedInstitutions", 0) or 0
        )

        structural_stable = finalized == current
        semantic_stable = enforced == finalized
        if structural_stable and semantic_stable:
            diagnostics["passed"] = True
            return enforced, diagnostics
        current = enforced

    diagnostics["passed"] = False
    raise RuntimeError(
        f"venture profile gates did not reach a shared fixed point within {max_cycles} cycles"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--max-cycles", type=int, default=6)
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    stable, diagnostics = stabilize_snapshot(
        payload,
        args.catalog.read_text(encoding="utf-8"),
        max_cycles=max(1, args.max_cycles),
    )
    rendered = json.dumps(stable, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the shared terminal fixed point.")
            return 1
        print("Venture profile snapshot passed the shared terminal fixed-point check.")
        return 0
    if rendered == current:
        print("No cross-gate venture profile changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(Path(__file__).resolve().parents[1])}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
