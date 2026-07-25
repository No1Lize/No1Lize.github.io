#!/usr/bin/env python3
"""One-time patch making venture project evidence entity-bound and stable."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("refine_venture_research_evidence.py")

OLD = '''    evidence = [profile.get("background", ""), profile.get("technology", ""), *non_capital_articles]
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

NEW = '''    # Only stable, entity-bound inputs may feed derived project fields.
    # ``profile.background`` is overwritten by this function, so using it as
    # evidence creates a two-pass oscillation on the production snapshot.
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


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Stable entity-bound project evidence selection already applied.")
        return
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected one project evidence block, found {count}")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied stable entity-bound project evidence selection.")


if __name__ == "__main__":
    main()
