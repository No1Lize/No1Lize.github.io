#!/usr/bin/env python3
"""Small follow-up patches for the tracked entity research record integration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{relative}: patch target not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    "  GitBranch,\n  UserRound,",
    "  GitBranch,\n  Star,\n  UserRound,",
)
