#!/usr/bin/env python3
"""Drive structural and entity-semantic venture gates to one shared fixed point."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from .enforce_venture_entity_semantics import enforce_snapshot
    from .finalize_venture_profiles import finalize_snapshot
except ImportError:
    from enforce_venture_entity_semantics import enforce_snapshot
    from finalize_venture_profiles import finalize_snapshot


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"


def _diff_paths(
    left: Any,
    right: Any,
    *,
    prefix: str = "$",
    limit: int = 40,
) -> list[str]:
    """Return bounded JSON-style paths whose values differ."""
    result: list[str] = []

    def visit(a: Any, b: Any, path: str) -> None:
        if len(result) >= limit:
            return
        if type(a) is not type(b):
            result.append(path)
            return
        if isinstance(a, dict):
            for key in sorted(set(a) | set(b), key=str):
                child = f"{path}.{key}"
                if key not in a or key not in b:
                    result.append(child)
                else:
                    visit(a[key], b[key], child)
                if len(result) >= limit:
                    return
            return
        if isinstance(a, list):
            if len(a) != len(b):
                result.append(f"{path}.length")
            for index, (left_item, right_item) in enumerate(zip(a, b)):
                visit(left_item, right_item, f"{path}[{index}]")
                if len(result) >= limit:
                    return
            return
        if a != b:
            result.append(path)

    visit(left, right, prefix)
    return result


def stabilize_snapshot(
    payload: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot accepted unchanged by both terminal quality gates.

    The structural finalizer and entity-semantic gate are individually
    deterministic, but one can expose a field that the other still normalizes.
    Alternate them until both are no-ops. Repeated states are treated as a real
    contract cycle rather than silently choosing one gate's output.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    current = copy.deepcopy(payload)
    seen: set[str] = set()
    history: list[dict[str, Any]] = []

    for pass_index in range(1, max_passes + 1):
        structural, structural_diagnostics = finalize_snapshot(current, catalog_text)
        semantic, semantic_diagnostics = enforce_snapshot(structural, catalog_text)

        structural_check, structural_check_diagnostics = finalize_snapshot(
            semantic, catalog_text
        )
        semantic_check, semantic_check_diagnostics = enforce_snapshot(
            semantic, catalog_text
        )

        structural_stable = structural_check == semantic
        semantic_stable = semantic_check == semantic
        history.append(
            {
                "pass": pass_index,
                "structuralStable": structural_stable,
                "semanticStable": semantic_stable,
                "structural": structural_diagnostics,
                "semantic": semantic_diagnostics,
                "structuralCheck": structural_check_diagnostics,
                "semanticCheck": semantic_check_diagnostics,
            }
        )
        if structural_stable and semantic_stable:
            return semantic, {
                "passes": pass_index,
                "converged": True,
                "history": history,
            }

        state_key = json.dumps(
            semantic,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        if state_key in seen:
            details = {
                "structuralVsSemantic": _diff_paths(semantic, structural_check),
                "semanticCheckVsSemantic": _diff_paths(semantic, semantic_check),
                "lastPass": history[-1],
            }
            raise RuntimeError(
                "venture terminal gates entered a cycle before reaching a shared "
                f"fixed point: {json.dumps(details, ensure_ascii=False, sort_keys=True)}"
            )
        seen.add(state_key)
        current = semantic

    details = {
        "structuralVsSemantic": _diff_paths(semantic, structural_check),
        "semanticCheckVsSemantic": _diff_paths(semantic, semantic_check),
        "lastPass": history[-1] if history else {},
    }
    raise RuntimeError(
        f"venture terminal gates did not converge within {max_passes} passes: "
        f"{json.dumps(details, ensure_ascii=False, sort_keys=True)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--max-passes", type=int, default=8)
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    stabilized, diagnostics = stabilize_snapshot(
        payload,
        args.catalog.read_text(encoding="utf-8"),
        max_passes=args.max_passes,
    )
    rendered = json.dumps(stabilized, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the shared terminal fixed point.")
            return 1
        print("Venture profile snapshot passed the shared terminal fixed-point check.")
        return 0

    if rendered == current:
        print("No venture profile stabilization changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
