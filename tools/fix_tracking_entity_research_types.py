#!/usr/bin/env python3
"""One-time cleanup for tracked entity research type compatibility."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

research = ROOT / "lib" / "tracking-entity-research.ts"
text = research.read_text(encoding="utf-8")
old = '''  companyMatch?: { slug?: string; confidence?: number };
  companyMatches?: { slug?: string; confidence?: number }[];'''
new = '''  companyMatch?: { slug: string; method: string; confidence: number };
  companyMatches?: { slug: string; method: string; confidence: number }[];'''
if new not in text:
    if old not in text:
        raise SystemExit("RawArticle company-match type patch target not found")
    research.write_text(text.replace(old, new, 1), encoding="utf-8")

page = ROOT / "app" / "tracking" / "entities" / "[type]" / "[slug]" / "page.tsx"
text = page.read_text(encoding="utf-8")
text = text.replace("  type TrackingResearchEntity,\n", "", 1)
page.write_text(text, encoding="utf-8")
