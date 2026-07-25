#!/usr/bin/env python3
"""Apply the curated-product parsing fix used by the venture sanitation pipeline."""

from __future__ import annotations

from pathlib import Path


TARGET = Path(__file__).with_name("sanitize_venture_profiles.py")
OLD = '''def _catalog_products(value: str) -> list[str]:
    parts = re.split(r"[、，,;/]|\\s+与\\s+|\\s+and\\s+", clean_text(value, 800), flags=re.IGNORECASE)
    return sanitize_product_items([part.strip() for part in parts if part.strip()])
'''
NEW = '''def _catalog_products(value: str) -> list[str]:
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


def main() -> int:
    text = TARGET.read_text(encoding="utf-8")
    if NEW in text:
        print("Curated venture product parsing is already patched.")
        return 0
    if OLD not in text:
        raise SystemExit("Expected curated-product parser block was not found.")
    TARGET.write_text(text.replace(OLD, NEW, 1), encoding="utf-8")
    print("Applied curated venture product parsing fix.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
