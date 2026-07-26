#!/usr/bin/env python3
"""Reject sentence fragments that superficially resemble Latin person names."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "tools" / "enforce_venture_entity_semantics.py"
TESTS = ROOT / "tests" / "test_venture_entity_semantics.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        TARGET,
        '''    "chief", "officer", "president", "executive",
''',
        '''    "chief", "officer", "president", "executive",
    "the", "next", "black", "history",
''',
        "person navigation tokens",
    )
    replace_once(
        TARGET,
        '''    if lowered & PERSON_NOISE_TOKENS:
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
''',
        '''    if lowered & PERSON_NOISE_TOKENS:
        return False
    if any("." in token and len(token.strip(".")) > 1 for token in tokens):
        return False
    if not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[0]) or not PERSON_LATIN_TOKEN_RE.fullmatch(tokens[-1]):
''',
        "sentence-fragment punctuation guard",
    )
    replace_once(
        TESTS,
        '''                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
''',
        '''                        {"name": "Spotlight Megan Holston-Alexander Hear", "role": "Partner"},
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                        {"name": "Chris Lyons. Black History", "role": "Partner"},
                        {"name": "Megan Holston-Alexander", "role": "Partner"},
''',
        "sentence-like person regression fixtures",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(diagnostics["removedTeamMembers"], 2)
''',
        '''        self.assertEqual(diagnostics["removedTeamMembers"], 4)
''',
        "team removal regression count",
    )


if __name__ == "__main__":
    main()
