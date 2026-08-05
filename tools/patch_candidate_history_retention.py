#!/usr/bin/env python3
"""One-time patch retaining reviewed candidates after formal registry publication."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "tools" / "build_company_candidates.py"
text = path.read_text(encoding="utf-8")
old = "            if not key or key in known:\n                continue"
new = "            if not key or (key in known and key not in decisions):\n                continue"
if new not in text:
    if old not in text:
        raise SystemExit("candidate retention patch target not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
