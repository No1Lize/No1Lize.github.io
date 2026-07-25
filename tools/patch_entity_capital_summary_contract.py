#!/usr/bin/env python3
"""Make entity-semantic and structural finalizers emit identical capital summaries."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SEMANTICS = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_function(path: Path, name: str, next_name: str, block: str) -> None:
    text = path.read_text(encoding="utf-8")
    start = text.find(f"def {name}(")
    end = text.find(f"\n\ndef {next_name}(", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{name}: function boundary not found")
    if block.rstrip() in text:
        print(f"{name}: already aligned")
        return
    path.write_text(text[:start] + block.rstrip() + text[end:], encoding="utf-8")
    print(f"{name}: aligned")


def main() -> None:
    block = '''def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    latest = sorted(
        events,
        key=lambda row: clean_text(row.get("date"), 20),
        reverse=True,
    )[0] if events else {}
    amounts = list(
        dict.fromkeys(
            clean_text(row.get("amount"), 80)
            for row in events
            if clean_text(row.get("amount"), 80)
        )
    )[:12]
    rounds = list(
        dict.fromkeys(
            clean_text(row.get("round"), 80)
            for row in events
            if clean_text(row.get("round"), 80)
        )
    )[:12]
    investors = list(
        dict.fromkeys(
            clean_text(item, 120)
            for row in events
            for item in (
                row.get("investors", [])
                if isinstance(row.get("investors"), list)
                else []
            )
            if clean_text(item, 120)
        )
    )[:20]
    if events:
        summary = (
            f"共识别到{len(events)}条可追溯融资记录；"
            f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    else:
        summary = "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    return {
        "eventCount": len(events),
        "disclosedAmounts": amounts,
        "rounds": rounds,
        "majorInvestors": investors,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }'''
    replace_function(SEMANTICS, "_capital_summary", "_enforce_snapshot_once", block)

    tests = TESTS.read_text(encoding="utf-8")
    if "from tools import finalize_venture_profiles as finalizer" not in tests:
        tests = tests.replace(
            "from tools import enforce_venture_entity_semantics as semantics\n",
            "from tools import enforce_venture_entity_semantics as semantics\nfrom tools import finalize_venture_profiles as finalizer\n",
            1,
        )
    marker = '''    def test_keeps_entity_subject_financing(self) -> None:
'''
    addition = '''    def test_capital_summary_matches_structural_finalizer(self) -> None:
        events = [
            {
                "date": "2026-07-20",
                "title": "Anthropic raises a new round",
                "amount": "$2 billion",
                "round": "Growth",
                "investors": ["Example Capital"],
            }
        ]
        self.assertEqual(
            semantics._capital_summary(events),
            finalizer._capital_summary(events),
        )
        self.assertEqual(
            semantics._capital_summary([]),
            finalizer._capital_summary([]),
        )

'''
    if "def test_capital_summary_matches_structural_finalizer" not in tests:
        if marker not in tests:
            raise SystemExit("capital summary test insertion point not found")
        tests = tests.replace(marker, addition + marker, 1)
    TESTS.write_text(tests, encoding="utf-8")
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
