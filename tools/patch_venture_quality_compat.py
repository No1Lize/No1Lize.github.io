#!/usr/bin/env python3
"""Make the final venture migration tolerate equivalent concurrent fixes."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("patch_venture_structured_products.py")
OLD = '''    replace_once(CRAWLER, old, new, "crawler team quality projection")
'''
NEW = '''    crawler_text = CRAWLER.read_text(encoding="utf-8")
    if "def _team_core_rows(" in crawler_text:
        print("crawler team quality projection: equivalent fix already applied")
    else:
        replace_once(CRAWLER, old, new, "crawler team quality projection")
'''


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Venture migration compatibility patch already applied.")
        return 0
    if OLD not in text:
        raise SystemExit("Crawler compatibility insertion point not found.")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied venture migration compatibility patch.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
