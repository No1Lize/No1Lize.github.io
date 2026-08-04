#!/usr/bin/env python3
"""Drive all deterministic venture publication gates to one shared fixed point."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

try:
    from .normalize_venture_profiles import normalize_payload
    from .stabilize_venture_profiles import stabilize_snapshot as stabilize_terminal_snapshot
    from .stabilize_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_evidence_snapshot,
    )
except ImportError:
    from normalize_venture_profiles import normalize_payload
    from stabilize_venture_profiles import stabilize_snapshot as stabilize_terminal_snapshot
    from stabilize_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_evidence_snapshot,
    )


EvidenceStabilizer = Callable[..., tuple[dict[str, Any], dict[str, Any]]]
Normalizer = Callable[[dict[str, Any], str], tuple[dict[str, Any], dict[str, Any]]]
TerminalStabilizer = Callable[..., tuple[dict[str, Any], dict[str, Any]]]


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def stabilize_publication_snapshot(
    snapshot: dict[str, Any],
    articles: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
    evidence_stabilizer: EvidenceStabilizer = stabilize_evidence_snapshot,
    normalizer: Normalizer = normalize_payload,
    terminal_stabilizer: TerminalStabilizer = stabilize_terminal_snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot unchanged by every deterministic publication gate.

    Evidence alignment, cross-entity normalization, and terminal structural /
    entity-semantic cleanup are deterministic in isolation. One layer can still
    expose fields that another layer subsequently rewrites, so the full sequence
    is repeated until every layer individually leaves the same candidate
    unchanged. A repeated non-stable state is treated as a real cross-gate cycle.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    current = copy.deepcopy(snapshot)
    seen = {_state_key(current)}
    history: list[dict[str, Any]] = []

    for pass_index in range(1, max_passes + 1):
        evidence, evidence_diagnostics = evidence_stabilizer(
            current,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        normalized, normalization_diagnostics = normalizer(
            copy.deepcopy(evidence), catalog_text
        )
        candidate, terminal_diagnostics = terminal_stabilizer(
            normalized,
            catalog_text,
            max_passes=max_passes,
        )

        evidence_check, evidence_check_diagnostics = evidence_stabilizer(
            candidate,
            articles,
            catalog_text,
            max_passes=max_passes,
        )
        normalized_check, normalization_check_diagnostics = normalizer(
            copy.deepcopy(candidate), catalog_text
        )
        terminal_check, terminal_check_diagnostics = terminal_stabilizer(
            candidate,
            catalog_text,
            max_passes=max_passes,
        )

        evidence_stable = evidence_check == candidate
        normalization_stable = normalized_check == candidate
        terminal_stable = terminal_check == candidate
        changed = candidate != current
        history.append(
            {
                "pass": pass_index,
                "changed": changed,
                "evidenceStable": evidence_stable,
                "normalizationStable": normalization_stable,
                "terminalStable": terminal_stable,
                "evidence": evidence_diagnostics,
                "normalization": normalization_diagnostics,
                "terminal": terminal_diagnostics,
                "evidenceCheck": evidence_check_diagnostics,
                "normalizationCheck": normalization_check_diagnostics,
                "terminalCheck": terminal_check_diagnostics,
            }
        )

        if evidence_stable and normalization_stable and terminal_stable:
            return candidate, {
                "passes": pass_index,
                "changedPasses": sum(bool(item["changed"]) for item in history),
                "converged": True,
                "history": history,
            }

        state_key = _state_key(candidate)
        if state_key in seen:
            raise RuntimeError(
                "venture publication gates entered a cycle before reaching a shared fixed point"
            )
        seen.add(state_key)
        current = candidate

    raise RuntimeError(
        f"venture publication gates did not converge within {max_passes} passes"
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
    stabilized, diagnostics = stabilize_publication_snapshot(
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
            print("Venture profile snapshot has not reached the shared publication fixed point.")
            return 1
        print("Venture profile snapshot passed the shared publication fixed-point check.")
        return 0

    if rendered == current:
        print("No venture publication fixed-point changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
