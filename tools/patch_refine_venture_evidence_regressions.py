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

NEW = '''    # Keep an existing field when it remains both entity-bound and
    # semantically valid. Otherwise derive it from stable inputs only.
    # ``profile.background`` is overwritten by this function, so feeding it
    # back into selection creates a two-pass oscillation on production data.
    stable_evidence = [
        company.summary,
        profile.get("technology", ""),
        *non_capital_articles,
    ]
    existing_problem = sanitize_narrative(
        current.get("problemSolved", ""), limit=460
    )
    if (
        existing_problem
        and _contains_any(existing_problem, PROBLEM_TERMS)
        and _contains_any(existing_problem, company.aliases)
    ):
        problem = existing_problem
    else:
        problem = _select_required_sentence(
            stable_evidence,
            required_aliases=company.aliases,
            required_terms=PROBLEM_TERMS,
            excluded_pattern=CAPITAL_MARKET_RE,
            limit=460,
        )

    existing_market = sanitize_narrative(
        current.get("marketOpportunity", ""), limit=460
    )
    if (
        existing_market
        and _contains_any(existing_market, MARKET_TERMS)
        and _contains_any(existing_market, company.aliases)
    ):
        market = existing_market
    else:
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
