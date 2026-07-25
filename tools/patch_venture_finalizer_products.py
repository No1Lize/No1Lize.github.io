#!/usr/bin/env python3
"""One-time patch aligning finalizer products with canonical normalization."""

from pathlib import Path

PATH = Path(__file__).with_name("finalize_venture_profiles.py")

IMPORT_ANCHOR = '''    from venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )


ROOT = Path(__file__).resolve().parents[1]
'''

IMPORT_REPLACEMENT = '''    from venture_profile_extraction import (
        clean_text,
        evidence_score,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )

try:
    from .normalize_venture_profiles import normalize_product_items
except ImportError:
    from normalize_venture_profiles import normalize_product_items


ROOT = Path(__file__).resolve().parents[1]
'''

PRODUCT_ANCHOR = '''def finalize_products(values: Sequence[Any], catalog_product: str) -> list[str]:
    normalized_catalog = re.sub(r"\s*与\s*", "、", catalog_product)
    products = sanitize_products(values, normalized_catalog)
    return [
        item
        for item in products
        if _compact(item) not in {_compact(label) for label in PURE_RESEARCH_LABELS}
    ][:10]
'''

PRODUCT_REPLACEMENT = '''def finalize_products(values: Sequence[Any], catalog_product: str) -> list[str]:
    normalized_catalog = re.sub(r"\s*与\s*", "、", catalog_product)
    products = normalize_product_items(sanitize_products(values, normalized_catalog))
    return [
        item
        for item in products
        if _compact(item) not in {_compact(label) for label in PURE_RESEARCH_LABELS}
    ][:10]
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one anchor, found {count}")
    return text.replace(old, new, 1)


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(text, IMPORT_ANCHOR, IMPORT_REPLACEMENT, "normalizer import")
    text = replace_once(text, PRODUCT_ANCHOR, PRODUCT_REPLACEMENT, "finalizer products")
    PATH.write_text(text, encoding="utf-8")
    print("Aligned finalizer products with canonical normalization.")


if __name__ == "__main__":
    main()
