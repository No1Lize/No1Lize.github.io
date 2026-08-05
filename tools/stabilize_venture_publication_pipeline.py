#!/usr/bin/env python3
"""Drive all deterministic venture publication gates to one shared fixed point."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Callable

try:
    from . import enforce_venture_entity_semantics as entity_semantics
    from . import refine_venture_research_evidence as research_evidence
    from .normalize_venture_publication import normalize_publication_payload
    from .stabilize_venture_profiles import stabilize_snapshot as stabilize_terminal_snapshot
    from .stabilize_venture_research_evidence import (
        ARTICLE_PATH,
        CATALOG_PATH,
        SNAPSHOT_PATH,
        stabilize_evidence_snapshot,
    )
except ImportError:
    import enforce_venture_entity_semantics as entity_semantics
    import refine_venture_research_evidence as research_evidence
    from normalize_venture_publication import normalize_publication_payload
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

# Evidence routing and terminal subject validation must recognize the same
# capital-market actions. If one gate treats an article as financing while the
# other treats it as a merger/listing, the shared publication pipeline can
# oscillate forever. Keep this pattern in the orchestrator and install the same
# compiled object into both modules before every fixed-point run.
CROSS_GATE_CAPITAL_ACTION_RE = re.compile(
    r"(?:\bipo\b|\binitial public offering\b|\blisted\b|\blisted on\b|"
    r"\blisting\b|\blisting on\b|\bwent public\b|\bgo(?:es|ing)? public\b|"
    r"\bbecom(?:e|es|ing) (?:a )?public company\b|\bpublic market\b|"
    r"\bnasdaq\b|\bnyse\b|\bhkex\b|\bstock exchange\b|"
    r"\bacquired\b|\bacquired by\b|\bacquisition\b|"
    r"\bmerg(?:e|ed|er|ers|ing)\b|\bbusiness combination\b|\bdelisted\b|"
    r"上市|挂牌|港股上市|美股上市|交易所|公开市场|并购|收购|退出|退市)",
    re.IGNORECASE,
)


def align_capital_event_patterns() -> None:
    """Install one capital-event vocabulary across the two mutable gates."""

    research_evidence.CAPITAL_MARKET_RE = CROSS_GATE_CAPITAL_ACTION_RE
    entity_semantics.CAPITAL_ACTION_RE = CROSS_GATE_CAPITAL_ACTION_RE


def _state_key(payload: dict[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _preview(value: Any, limit: int = 180) -> str:
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rendered if len(rendered) <= limit else rendered[: limit - 1] + "…"


def _diff_paths(
    left: Any,
    right: Any,
    *,
    prefix: str = "$",
    limit: int = 30,
) -> list[dict[str, str]]:
    """Return a bounded set of JSON-style paths changed by one gate."""
    differences: list[dict[str, str]] = []

    def visit(before: Any, after: Any, path: str) -> None:
        if len(differences) >= limit or before == after:
            return
        if isinstance(before, dict) and isinstance(after, dict):
            keys = sorted(set(before) | set(after), key=str)
            for key in keys:
                if len(differences) >= limit:
                    break
                child_path = f"{path}.{key}"
                if key not in before:
                    differences.append(
                        {"path": child_path, "before": "<missing>", "after": _preview(after[key])}
                    )
                elif key not in after:
                    differences.append(
                        {"path": child_path, "before": _preview(before[key]), "after": "<missing>"}
                    )
                else:
                    visit(before[key], after[key], child_path)
            return
        if isinstance(before, list) and isinstance(after, list):
            shared = min(len(before), len(after))
            for index in range(shared):
                if len(differences) >= limit:
                    break
                visit(before[index], after[index], f"{path}[{index}]")
            for index in range(shared, max(len(before), len(after))):
                if len(differences) >= limit:
                    break
                if index >= len(before):
                    differences.append(
                        {
                            "path": f"{path}[{index}]",
                            "before": "<missing>",
                            "after": _preview(after[index]),
                        }
                    )
                else:
                    differences.append(
                        {
                            "path": f"{path}[{index}]",
                            "before": _preview(before[index]),
                            "after": "<missing>",
                        }
                    )
            return
        differences.append(
            {"path": path, "before": _preview(before), "after": _preview(after)}
        )

    visit(left, right, prefix)
    return differences


def stabilize_publication_snapshot(
    snapshot: dict[str, Any],
    articles: dict[str, Any],
    catalog_text: str,
    *,
    max_passes: int = 8,
    evidence_stabilizer: EvidenceStabilizer = stabilize_evidence_snapshot,
    normalizer: Normalizer = normalize_publication_payload,
    terminal_stabilizer: TerminalStabilizer = stabilize_terminal_snapshot,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a snapshot unchanged by every deterministic publication gate.

    Evidence alignment, publication-aware normalization, and terminal structural /
    entity-semantic cleanup are deterministic in isolation. One layer can still
    expose fields that another layer subsequently rewrites, so the full sequence
    is repeated until every layer individually leaves the same candidate
    unchanged. A repeated non-stable state is treated as a real cross-gate cycle.
    """
    if max_passes < 1:
        raise ValueError("max_passes must be positive")

    align_capital_event_patterns()
    current = copy.deepcopy(snapshot)
    seen: dict[str, int] = {_state_key(current): 0}
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
        gate_diffs = {
            "evidence": _diff_paths(candidate, evidence_check),
            "normalization": _diff_paths(candidate, normalized_check),
            "terminal": _diff_paths(candidate, terminal_check),
        }
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
                "gateDiffs": gate_diffs,
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
            cycle = {
                "repeatedFromPass": seen[state_key],
                "repeatedAtPass": pass_index,
                "evidenceStable": evidence_stable,
                "normalizationStable": normalization_stable,
                "terminalStable": terminal_stable,
                "gateDiffs": gate_diffs,
            }
            raise RuntimeError(
                "venture publication gates entered a cycle before reaching a shared fixed point: "
                + json.dumps(cycle, ensure_ascii=False, sort_keys=True)
            )
        seen[state_key] = pass_index
        current = candidate

    last = history[-1] if history else {}
    raise RuntimeError(
        f"venture publication gates did not converge within {max_passes} passes: "
        + json.dumps(last.get("gateDiffs", {}), ensure_ascii=False, sort_keys=True)
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
