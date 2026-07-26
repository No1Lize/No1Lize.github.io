#!/usr/bin/env python3
"""Apply the stable, entity-bound venture background evidence fix once."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "refine_venture_research_evidence.py"
TEST = ROOT / "tests" / "test_refine_venture_research_evidence.py"

OLD_SOURCE = '''    evidence = [
        profile.get("background", ""),
        profile.get("technology", ""),
        profile.get("researchTechnology", ""),
        *non_capital_articles,
    ]
    problem = _select_required_sentence(
        evidence,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        evidence,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
'''

NEW_SOURCE = '''    # Derived project fields must use stable, entity-bound evidence only.
    # ``profile.background`` is overwritten below, so feeding it back into this
    # selection creates a two-pass oscillation in production snapshots.
    stable_evidence = [
        company.summary,
        profile.get("technology", ""),
        *non_capital_articles,
    ]
    problem = _select_required_sentence(
        stable_evidence,
        required_aliases=company.aliases,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        stable_evidence,
        required_aliases=company.aliases,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
'''

TEST_METHOD = '''
    def test_project_background_does_not_feed_mutable_background_back(self) -> None:
        snapshot = copy.deepcopy(self.snapshot)
        snapshot["companies"]["agibot"]["background"] = (
            "智元机器人是一家具身智能机器人公司。"
            "智元机器人面向制造业客户提供具身智能机器人解决方案并推动规模化部署。"
        )

        first, _ = refine_snapshot(snapshot, self.articles, CATALOG)
        second, _ = refine_snapshot(copy.deepcopy(first), self.articles, CATALOG)

        self.assertEqual(first, second)
        self.assertEqual(
            first["companies"]["agibot"]["projectBackground"]["problemSolved"],
            "",
        )
        self.assertEqual(
            first["companies"]["agibot"]["projectBackground"]["marketOpportunity"],
            "",
        )
'''


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"expected source block not found in {path}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(SOURCE, OLD_SOURCE, NEW_SOURCE)

    test_text = TEST.read_text(encoding="utf-8")
    if "test_project_background_does_not_feed_mutable_background_back" not in test_text:
        marker = '\n\nif __name__ == "__main__":\n'
        if marker not in test_text:
            raise SystemExit("test insertion marker not found")
        TEST.write_text(test_text.replace(marker, TEST_METHOD + marker, 1), encoding="utf-8")


if __name__ == "__main__":
    main()
