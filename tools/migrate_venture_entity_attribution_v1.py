#!/usr/bin/env python3
"""Apply entity-attribution and editorial-product fixes to the venture finalizer."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
TESTS = ROOT / "tests" / "test_finalize_venture_profiles.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    if old not in text:
        raise SystemExit(f"{label}: expected block not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_finalizer() -> None:
    old_noise = '''    "contact",
    "careers",
    "招聘",
'''
    new_noise = '''    "contact",
    "careers",
    "press release",
    "latest news",
    "newsroom",
    "things to know",
    "crew undocks",
    "journey home",
    "招聘",
'''
    replace_once(FINALIZER, old_noise, new_noise, "editorial product phrases")

    old_regex = '''    r"(?:融资|募资|领投|跟投|战略投资|估值)",
'''
    new_regex = '''    r"(?:融资|募资|领投|跟投|战略投资)",
'''
    replace_once(FINALIZER, old_regex, new_regex, "strong financing evidence")

    old_functions = '''def finalize_financing(values: Sequence[Any]) -> list[dict[str, Any]]:
    candidates = sanitize_capital_events(values, capital_market=False)
    result: list[dict[str, Any]] = []
    for row in candidates:
        evidence = f"{row.get('title', '')} {row.get('summary', '')}"
        investors = row.get("investors", []) if isinstance(row.get("investors"), list) else []
        has_explicit_action = bool(STRONG_FINANCING_RE.search(evidence))
        has_supported_investment = bool(
            INVESTED_IN_RE.search(evidence)
            and (row.get("amount") or row.get("round") or investors)
        )
        if has_explicit_action or has_supported_investment:
            result.append(row)
    return result[:20]


def finalize_capital_markets(values: Sequence[Any]) -> list[dict[str, Any]]:
    return [
        row
        for row in sanitize_capital_events(values, capital_market=True)
        if CAPITAL_EVIDENCE_RE.search(f"{row.get('title', '')} {row.get('summary', '')}")
    ][:20]
'''
    new_functions = '''def _event_targets_entity(row: dict[str, Any], aliases: Sequence[str]) -> bool:
    normalized_aliases = [
        clean_text(alias, 120).casefold()
        for alias in aliases
        if len(_compact(alias)) >= 2
    ]
    if not normalized_aliases:
        return True
    title = clean_text(row.get("title"), 260).casefold()
    summary = clean_text(row.get("summary"), 700).casefold()
    title_subject = title[:64]
    summary_subject = summary[:96]
    return any(
        alias in title_subject or alias in summary_subject
        for alias in normalized_aliases
    )


def finalize_financing(
    values: Sequence[Any], aliases: Sequence[str] = ()
) -> list[dict[str, Any]]:
    candidates = sanitize_capital_events(values, capital_market=False)
    result: list[dict[str, Any]] = []
    for row in candidates:
        if not _event_targets_entity(row, aliases):
            continue
        evidence = f"{row.get('title', '')} {row.get('summary', '')}"
        investors = row.get("investors", []) if isinstance(row.get("investors"), list) else []
        has_explicit_action = bool(STRONG_FINANCING_RE.search(evidence))
        has_supported_investment = bool(
            INVESTED_IN_RE.search(evidence)
            and (row.get("amount") or row.get("round") or investors)
        )
        if has_explicit_action or has_supported_investment:
            result.append(row)
    return result[:20]


def finalize_capital_markets(
    values: Sequence[Any], aliases: Sequence[str] = ()
) -> list[dict[str, Any]]:
    return [
        row
        for row in sanitize_capital_events(values, capital_market=True)
        if _event_targets_entity(row, aliases)
        and CAPITAL_EVIDENCE_RE.search(f"{row.get('title', '')} {row.get('summary', '')}")
    ][:20]
'''
    replace_once(FINALIZER, old_functions, new_functions, "event entity attribution")

    old_calls = '''        profile["financing"] = finalize_financing(profile.get("financing", []))
        profile["capitalMarkets"] = finalize_capital_markets(profile.get("capitalMarkets", []))
'''
    new_calls = '''        profile["financing"] = finalize_financing(profile.get("financing", []), aliases)
        profile["capitalMarkets"] = finalize_capital_markets(
            profile.get("capitalMarkets", []), aliases
        )
'''
    replace_once(FINALIZER, old_calls, new_calls, "entity-aware finalizer calls")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''    def test_recent_investments_use_actual_one_year_window(self) -> None:
'''
    addition = '''    def test_financing_rejects_other_company_round(self) -> None:
        rows = finalizer.finalize_financing(
            [
                {
                    "date": "2026-07-20",
                    "type": "融资",
                    "title": "Inference startup Infinity raises $15M from Anthropic researchers",
                    "summary": "Infinity announced a $15 million raise with participation from Anthropic researchers.",
                    "amount": "$15 million",
                    "sourceUrl": "https://example.com/infinity",
                }
            ],
            ("Anthropic",),
        )
        self.assertEqual(rows, [])

    def test_products_reject_news_title_labels(self) -> None:
        products = finalizer.finalize_products(
            ["15 Things to Know about Ax-1", "Ax-1 Crew Undocks from ISS", "Axiom Station"],
            "Axiom Station、私人宇航任务",
        )
        self.assertEqual(products, ["Axiom Station", "私人宇航任务"])

'''
    if "def test_financing_rejects_other_company_round" not in text:
        if marker not in text:
            raise SystemExit("test insertion marker not found")
        TESTS.write_text(text.replace(marker, addition + marker, 1), encoding="utf-8")
        print("entity-attribution regressions: applied")
    else:
        print("entity-attribution regressions: already applied")


def main() -> int:
    patch_finalizer()
    patch_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
