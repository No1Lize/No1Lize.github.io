#!/usr/bin/env python3
"""Preserve short catalog summaries when narrative cleanup returns empty."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("enforce_venture_entity_semantics.py")
OLD = '''        if not background and spec:
            background = sanitize_narrative(spec.summary, limit=900)
'''
NEW = '''        if not background and spec:
            background = (
                sanitize_narrative(spec.summary, limit=900)
                or clean_text(spec.summary, 900)
            )
'''


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Short venture catalog-summary fallback already applied.")
        return
    count = text.count(OLD)
    if count != 1:
        raise SystemExit(f"expected one background fallback block, found {count}")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied short venture catalog-summary fallback.")


if __name__ == "__main__":
    main()
