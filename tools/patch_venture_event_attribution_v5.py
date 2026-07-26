#!/usr/bin/env python3
"""Tighten financing and capital-event subject attribution."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_function(text: str, name: str, next_name: str, block: str) -> str:
    if block.rstrip() in text:
        print(f"{name}: already applied")
        return text
    start = text.find(f"def {name}(")
    end = text.find(f"\n\ndef {next_name}(", start)
    if start < 0 or end < 0:
        raise SystemExit(f"{name}: function boundary not found")
    print(f"{name}: replaced")
    return text[:start] + block.rstrip() + text[end:]


def patch_semantics() -> None:
    text = TARGET.read_text(encoding="utf-8")
    block = '''def _subject_evidence(
    row: dict[str, Any],
    aliases: Sequence[str],
    official_domain: str,
    action_re: re.Pattern[str],
) -> bool:
    title = clean_text(row.get("title"), 500)
    summary = clean_text(row.get("summary"), 1200)
    evidence = f"{title} {summary}".strip()
    action = action_re.search(evidence)
    if not evidence or action is None:
        return False

    lowered = evidence.casefold()
    source_is_official = bool(
        official_domain and _domain(row.get("sourceUrl")) == official_domain
    )
    title_lowered = title.casefold()
    title_has_alias = any(
        len(_compact(alias)) >= 2 and alias.casefold() in title_lowered
        for alias in aliases
    )
    title_has_action = action_re.search(title) is not None

    # Third-party media rows must identify both the entity and event in the title.
    # This rejects clickbait headlines whose body merely mentions an acquisition.
    if not source_is_official and not (title_has_alias and title_has_action):
        return False

    alias_positions = [
        lowered.find(alias.casefold())
        for alias in aliases
        if len(_compact(alias)) >= 2 and alias.casefold() in lowered
    ]
    if not alias_positions:
        return bool(source_is_official and FIRST_PERSON_FINANCING_RE.search(evidence))

    alias_position = min(alias_positions)
    if alias_position <= action.start() + 8:
        return True

    prefix = lowered[max(0, alias_position - 45) : alias_position]
    if RELATIONAL_MENTION_RE.search(prefix):
        return False

    for alias in aliases:
        escaped = re.escape(alias.casefold())
        if re.search(
            rf"(?:investment|funding|financing).{{0,32}}(?:in|for|of)\s+{escaped}",
            lowered,
        ):
            return True
        if re.search(rf"(?:对|向){escaped}.{{0,18}}(?:投资|融资)", lowered):
            return True

    # An official news index is not enough by itself. Without direct subject
    # evidence, only an explicit first-person disclosure is accepted.
    return bool(source_is_official and FIRST_PERSON_FINANCING_RE.search(evidence))
'''
    text = replace_function(text, "_subject_evidence", "_sanitize_events", block)
    TARGET.write_text(text, encoding="utf-8")


def patch_tests() -> None:
    text = TESTS.read_text(encoding="utf-8")
    marker = '''    def test_trims_investor_relations_page_chrome(self) -> None:
'''
    addition = '''    def test_rejects_official_aggregation_and_clickbait_capital_events(self) -> None:
        payload = {
            "companies": {
                "anthropic": {
                    "slug": "anthropic",
                    "name": "Anthropic",
                    "background": "Anthropic builds reliable AI systems.",
                    "technology": "Anthropic develops Claude Platform.",
                    "products": ["Claude Platform"],
                    "team": [],
                    "financing": [{
                        "date": "2021-03-19",
                        "title": "Newsroom",
                        "summary": (
                            "A founder raised $900M before a later mention of Anthropic."
                        ),
                        "sourceUrl": "https://www.anthropic.com/newsroom",
                    }],
                    "capitalMarkets": [{
                        "date": "2026-07-11",
                        "title": "AI史诗级工程却引来愤怒",
                        "summary": "Anthropic announced the acquisition of Bun.",
                        "sourceUrl": "https://news.example.com/clickbait",
                    }],
                    "technologyProducts": [],
                    "sources": [],
                }
            },
            "institutions": {},
            "qualityGate": {"passed": True, "checks": {}},
        }
        cleaned, diagnostics = semantics.enforce_snapshot(payload, CATALOG)
        company = cleaned["companies"]["anthropic"]
        self.assertEqual(company["financing"], [])
        self.assertEqual(company["capitalMarkets"], [])
        self.assertEqual(diagnostics["removedFinancing"], 1)
        self.assertEqual(diagnostics["removedCapitalMarkets"], 1)

'''
    if "def test_rejects_official_aggregation_and_clickbait_capital_events" not in text:
        if marker not in text:
            raise SystemExit("event attribution test marker not found")
        text = text.replace(marker, addition + marker, 1)
        print("event attribution regressions: applied")
    else:
        print("event attribution regressions: already applied")

    old = '''        self.assertEqual(cleaned["companies"]["form-energy"]["financing"], [])
'''
    new = '''        self.assertEqual(cleaned["companies"]["form-energy"]["financing"], [])
        self.assertEqual(cleaned["companies"]["anthropic"]["capitalMarkets"], [])
'''
    if new not in text:
        if old not in text:
            raise SystemExit("production event assertion marker not found")
        text = text.replace(old, new, 1)
        print("production event assertions: applied")

    TESTS.write_text(text, encoding="utf-8")


def main() -> None:
    patch_semantics()
    patch_tests()


if __name__ == "__main__":
    main()
