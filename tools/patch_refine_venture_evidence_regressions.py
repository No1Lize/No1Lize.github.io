#!/usr/bin/env python3
"""Fold the structural/entity shared fixed point into the terminal entity gate."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def main() -> None:
    text = SEMANTICS.read_text(encoding="utf-8")
    old = '''def enforce_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return the terminal semantic fixed point in one public invocation.

    Individual field transforms are deterministic and information-reducing, but
    some derived fields depend on values normalized earlier in the same pass.
    Iterating the private single pass prevents callers from having to invoke the
    publication gate repeatedly and makes ``--check`` a true terminal check.
    """
    current = copy.deepcopy(payload)
    aggregate: dict[str, int] = {}
    for pass_index in range(1, 6):
        next_payload, diagnostics = _enforce_snapshot_once(current, catalog_text)
        for key, value in diagnostics.items():
            if isinstance(value, int):
                aggregate[key] = aggregate.get(key, 0) + value
        aggregate["internalPasses"] = pass_index
        if next_payload == current:
            return next_payload, aggregate
        current = next_payload
    raise RuntimeError("entity-semantic enforcement did not converge within five passes")
'''
    new = '''def enforce_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    """Return a snapshot stable under both terminal publication gates.

    Structural and entity-semantic transforms enforce complementary contracts.
    The entity gate is the terminal orchestrator used by existing workflows, so
    it alternates both transforms until neither changes the snapshot.
    """
    try:
        from .finalize_venture_profiles import finalize_snapshot
    except ImportError:
        from finalize_venture_profiles import finalize_snapshot

    current = copy.deepcopy(payload)
    aggregate: dict[str, int] = {}
    for pass_index in range(1, 7):
        finalized, structural = finalize_snapshot(current, catalog_text)
        next_payload, semantic = _enforce_snapshot_once(finalized, catalog_text)
        for key, value in semantic.items():
            if isinstance(value, int):
                aggregate[key] = aggregate.get(key, 0) + value
        aggregate["structuralChangedCompanies"] = (
            aggregate.get("structuralChangedCompanies", 0)
            + int(structural.get("changedCompanies", 0) or 0)
        )
        aggregate["structuralChangedInstitutions"] = (
            aggregate.get("structuralChangedInstitutions", 0)
            + int(structural.get("changedInstitutions", 0) or 0)
        )
        aggregate["internalPasses"] = pass_index
        if finalized == current and next_payload == finalized:
            return next_payload, aggregate
        current = next_payload
    raise RuntimeError(
        "structural and entity-semantic gates did not converge within six passes"
    )
'''
    if new not in text:
        if old not in text:
            raise SystemExit("shared terminal gate source block not found")
        SEMANTICS.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("shared terminal gate: applied")
    else:
        print("shared terminal gate: already applied")

    tests = TESTS.read_text(encoding="utf-8")
    old_assert = '''        self.assertEqual(first, second)
        self.assertGreaterEqual(diagnostics["internalPasses"], 2)
        self.assertEqual(second_diagnostics["changedCompanies"], 0)
'''
    new_assert = '''        self.assertEqual(first, second)
        structurally_final, _ = finalizer.finalize_snapshot(
            copy.deepcopy(first), CATALOG
        )
        self.assertEqual(first, structurally_final)
        self.assertGreaterEqual(diagnostics["internalPasses"], 2)
        self.assertEqual(second_diagnostics["changedCompanies"], 0)
        self.assertEqual(second_diagnostics["structuralChangedCompanies"], 0)
'''
    if new_assert not in tests:
        if old_assert not in tests:
            raise SystemExit("shared terminal gate regression assertion not found")
        TESTS.write_text(tests.replace(old_assert, new_assert, 1), encoding="utf-8")
        print("shared terminal regression: applied")
    else:
        print("shared terminal regression: already applied")


if __name__ == "__main__":
    main()
