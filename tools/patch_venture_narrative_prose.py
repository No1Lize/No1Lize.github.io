#!/usr/bin/env python3
"""Reduce false positives in the venture narrative navigation heuristic."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("sanitize_venture_narratives.py")
OLD = '''    if len(tokens) >= 18 and short_tokens / max(1, len(tokens)) >= 0.85:
        if len(hits) >= 2 and not re.search(r"\\d", text):
            return True
'''
NEW = '''    if len(tokens) >= 18 and short_tokens / max(1, len(tokens)) >= 0.85:
        # Two ordinary prose words such as "research" and "company" are not
        # enough to classify a complete sentence as page navigation.
        if len(hits) >= 3 and not re.search(r"\\d", text):
            return True
'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Venture narrative prose heuristic is already patched.")
        return 0
    if OLD not in text:
        raise SystemExit("Expected narrative navigation heuristic was not found.")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied venture narrative prose heuristic fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
