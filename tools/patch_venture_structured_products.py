#!/usr/bin/env python3
"""Apply pending venture post-processing fixes before snapshot generation."""

from __future__ import annotations

from pathlib import Path


PRODUCT_TARGET = Path(__file__).with_name("sanitize_venture_profiles.py")
PRODUCT_OLD = '''def _catalog_products(value: str) -> list[str]:
    parts = re.split(r"[、，,;/]|\\s+与\\s+|\\s+and\\s+", clean_text(value, 800), flags=re.IGNORECASE)
    return sanitize_product_items([part.strip() for part in parts if part.strip()])
'''
PRODUCT_NEW = '''def _catalog_products(value: str) -> list[str]:
    parts = re.split(
        r"[、，,;/]|\\s+与\\s*|\\s+and\\s+",
        clean_text(value, 800),
        flags=re.IGNORECASE,
    )
    products = sanitize_product_items(
        [part.strip() for part in parts if part.strip()]
    )
    return [
        item
        for item in products
        if not (
            re.search(r"(?:研究|research)\\W*$", item, re.IGNORECASE)
            and not CONCRETE_PRODUCT_RE.search(item)
        )
    ]
'''

NARRATIVE_TARGET = Path(__file__).with_name("sanitize_venture_narratives.py")
NARRATIVE_OLD = '''    if len(tokens) >= 18 and short_tokens / max(1, len(tokens)) >= 0.85:
        if len(hits) >= 2 and not re.search(r"\\d", text):
            return True
'''
NARRATIVE_NEW = '''    if len(tokens) >= 18 and short_tokens / max(1, len(tokens)) >= 0.85:
        # Two ordinary prose words such as "research" and "company" are not
        # enough to classify a complete sentence as page navigation.
        if len(hits) >= 3 and not re.search(r"\\d", text):
            return True
'''


def _replace(path: Path, old: str, new: str, label: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label} is already patched.")
        return False
    if old not in text:
        raise SystemExit(f"Expected {label} block was not found.")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"Applied {label} fix.")
    return True


def main() -> int:
    _replace(PRODUCT_TARGET, PRODUCT_OLD, PRODUCT_NEW, "curated product parsing")
    _replace(NARRATIVE_TARGET, NARRATIVE_OLD, NARRATIVE_NEW, "narrative prose heuristic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
