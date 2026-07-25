#!/usr/bin/env python3
"""Resume the layered migration after fixing script-local imports."""

from __future__ import annotations

from pathlib import Path


MIGRATION = Path(__file__).with_name("patch_refine_venture_evidence_regressions.py")


def main() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    old = "    from tools.venture_profile_extraction import clean_text, parse_catalog\n"
    new = "    from venture_profile_extraction import clean_text, parse_catalog\n"
    if old in text:
        MIGRATION.write_text(text.replace(old, new, 1), encoding="utf-8")
        print("script-local venture extraction import: fixed")
    elif new in text:
        print("script-local venture extraction import: already fixed")
    else:
        raise SystemExit("snapshot reset import anchor not found")
    Path(__file__).unlink()


if __name__ == "__main__":
    main()
