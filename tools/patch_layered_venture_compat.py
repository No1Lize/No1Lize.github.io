#!/usr/bin/env python3
"""Make the terminal entity-semantic pass internally reach a fixed point."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def main() -> None:
    text = SEMANTICS.read_text(encoding="utf-8")
    old_signature = '''def enforce_snapshot(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
'''
    new_signature = '''def _enforce_snapshot_once(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
'''
    if new_signature not in text:
        if old_signature not in text:
            raise SystemExit("entity semantic function signature not found")
        text = text.replace(old_signature, new_signature, 1)

    marker = '''def main() -> int:
'''
    wrapper = '''def enforce_snapshot(
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
    if "def enforce_snapshot(\n    payload: dict[str, Any], catalog_text: str\n)" not in text:
        if marker not in text:
            raise SystemExit("entity semantic wrapper insertion point not found")
        text = text.replace(marker, wrapper + marker, 1)
    SEMANTICS.write_text(text, encoding="utf-8")

    tests = TESTS.read_text(encoding="utf-8")
    test_marker = '''    def test_is_idempotent(self) -> None:
'''
    regression = '''    def test_complex_snapshot_reaches_fixed_point_in_one_call(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems. Investor Relations Transfer Agent.",
                    "technology": "OpenAI models are discussed. Anthropic develops Claude models.",
                    "products": ["Claude 模型", "2025"],
                    "team": [],
                    "financing": [],
                    "capitalMarkets": [],
                    "technologyProducts": [
                        {
                            "name": "Claude 模型",
                            "description": "Unrelated OpenAI product description.",
                            "technicalHighlights": [],
                            "sourceUrl": "",
                        }
                    ],
                    "projectBackground": {
                        "summary": "Stale derived summary.",
                        "problemSolved": "Unrelated exercise collection.",
                        "marketOpportunity": "Anthropic serves enterprise AI users.",
                    },
                    "capitalSummary": {
                        "eventCount": 9,
                        "summary": "Stale capital summary.",
                    },
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        first, diagnostics = semantics.enforce_snapshot(copy.deepcopy(payload), CATALOG)
        second, second_diagnostics = semantics.enforce_snapshot(copy.deepcopy(first), CATALOG)
        self.assertEqual(first, second)
        self.assertGreaterEqual(diagnostics["internalPasses"], 2)
        self.assertEqual(second_diagnostics["changedCompanies"], 0)
        self.assertEqual(first["companies"]["anthropic"]["products"], ["Claude 模型"])
        self.assertEqual(first["companies"]["anthropic"]["capitalSummary"]["eventCount"], 0)

'''
    if "def test_complex_snapshot_reaches_fixed_point_in_one_call" not in tests:
        if test_marker not in tests:
            raise SystemExit("entity semantic regression insertion point not found")
        tests = tests.replace(test_marker, regression + test_marker, 1)
        TESTS.write_text(tests, encoding="utf-8")

    Path(__file__).unlink()
    print("entity semantic fixed-point wrapper and regression: applied")


if __name__ == "__main__":
    main()
