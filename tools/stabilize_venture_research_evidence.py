#!/usr/bin/env python3
"""Drive venture evidence alignment to a deterministic fixed point."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

try:
    from .refine_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        refine_snapshot,
    )
except ImportError:
    from refine_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        refine_snapshot,
    )


Refiner = Callable[
    [dict[str, Any], dict[str, Any], str],
    tuple[dict[str, Any], dict[str, int]],
]


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stabilize_evidence_snapshot(
    snapshot: dict[str, Any],
    articles: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
    refiner: Refiner = refine_snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot that a further evidence-refinement pass leaves unchanged."""
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    current = copy.deepcopy(snapshot)
    seen = {_state_key(current)}
    history: list[dict[str, Any]] = []
    totals: dict[str, int] = {}

    for pass_index in range(1, max_passes + 1):
        refined, diagnostics = refiner(current, articles, catalog_text)
        changed = refined != current
        history.append(
            {
                "pass": pass_index,
                "changed": changed,
                "diagnostics": diagnostics,
            }
        )
        for key, value in diagnostics.items():
            totals[key] = totals.get(key, 0) + int(value or 0)

        if not changed:
            return current, {
                "passes": pass_index,
                "changedPasses": pass_index - 1,
                "converged": True,
                "totals": totals,
                "history": history,
            }

        state_key = _state_key(refined)
        if state_key in seen:
            raise RuntimeError(
                "venture evidence alignment entered a cycle before reaching a fixed point"
            )
        seen.add(state_key)
        current = refined

    raise RuntimeError(
        f"venture evidence alignment did not converge within {max_passes} passes"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--max-passes", type=int, default=8)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    stabilized, diagnostics = stabilize_evidence_snapshot(
        snapshot,
        articles,
        args.catalog.read_text(encoding="utf-8"),
        max_passes=args.max_passes,
    )
    rendered = json.dumps(stabilized, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))

    if args.check:
        if rendered != current:
            print("Venture profile snapshot has not reached the evidence fixed point.")
            return 1
        print("Venture profile snapshot passed the evidence fixed-point check.")
        return 0

    if rendered == current:
        print("No venture evidence fixed-point changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
