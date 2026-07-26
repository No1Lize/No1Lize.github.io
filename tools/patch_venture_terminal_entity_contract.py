#!/usr/bin/env python3
"""Make structural and semantic venture gates share entity validators."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FINALIZER = ROOT / "tools" / "finalize_venture_profiles.py"
TESTS = ROOT / "tests" / "test_stabilize_venture_profiles.py"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def main() -> None:
    replace_once(
        FINALIZER,
        '''try:
    from .sanitize_venture_narratives import sanitize_narrative
''',
        '''try:
    from .enforce_venture_entity_semantics import _valid_person_name, _valid_product
    from .sanitize_venture_narratives import sanitize_narrative
''',
        "relative shared entity validators",
    )
    replace_once(
        FINALIZER,
        '''except ImportError:
    from sanitize_venture_narratives import sanitize_narrative
''',
        '''except ImportError:
    from enforce_venture_entity_semantics import _valid_person_name, _valid_product
    from sanitize_venture_narratives import sanitize_narrative
''',
        "script shared entity validators",
    )
    replace_once(
        FINALIZER,
        '''def finalize_products(values: Sequence[Any], catalog_product: str) -> list[str]:
    normalized_values = _split_product_values(values)
    normalized_catalog = "、".join(_split_product_values([catalog_product]))
    products = sanitize_products(normalized_values, normalized_catalog)
    return [item for item in products if not _product_noise(item)][:10]
''',
        '''def finalize_products(
    values: Sequence[Any],
    catalog_product: str,
    aliases: Sequence[str] = (),
) -> list[str]:
    normalized_values = _split_product_values(values)
    normalized_catalog = "、".join(_split_product_values([catalog_product]))
    products = sanitize_products(normalized_values, normalized_catalog)
    return [
        item
        for item in products
        if not _product_noise(item) and _valid_product(item, aliases)
    ][:10]
''',
        "structural product entity contract",
    )
    replace_once(
        FINALIZER,
        '''        if any(term in name.casefold() for term in TEAM_NAME_NOISE_TERMS):
            continue
''',
        '''        if (
            any(term in name.casefold() for term in TEAM_NAME_NOISE_TERMS)
            or not _valid_person_name(name)
        ):
            continue
''',
        "structural team entity contract",
    )
    replace_once(
        FINALIZER,
        '''        profile["products"] = finalize_products(profile.get("products", []), catalog_product)
''',
        '''        profile["products"] = finalize_products(
            profile.get("products", []), catalog_product, aliases
        )
''',
        "entity-aware structural product call",
    )

    replace_once(
        TESTS,
        '''                    "products": ["Lattice 平台与多类自主飞行器"],
                    "technologyProducts": [],
                    "team": [],
''',
        '''                    "products": [
                        "Anduril Industries",
                        "英特尔深化智能生态合作",
                        "Lattice 平台与多类自主飞行器",
                    ],
                    "technologyProducts": [],
                    "team": [
                        {"name": "Chris Lyons. The Next", "role": "Partner"},
                    ],
''',
        "shared fixed-point entity fixtures",
    )
    replace_once(
        TESTS,
        '''        self.assertEqual(company["products"], ["Lattice 平台", "多类自主飞行器"])
        self.assertEqual(structural_check, stabilized)
''',
        '''        self.assertEqual(company["products"], ["Lattice 平台", "多类自主飞行器"])
        self.assertEqual(company["team"], [])
        self.assertEqual(structural_check, stabilized)
''',
        "shared fixed-point entity assertions",
    )


if __name__ == "__main__":
    main()
