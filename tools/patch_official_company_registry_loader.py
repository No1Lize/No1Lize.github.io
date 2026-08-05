#!/usr/bin/env python3
"""One-time patch for official-company crawlers after catalog JSON migration."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: patch target not found")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


crawler = ROOT / "tools" / "crawl_official_companies.py"
replace_once(
    crawler,
    '''REGISTRY_PATH = ROOT / "config" / "official_company_sources.json"\nCATALOG_PATH = ROOT / "lib" / "catalog-data.ts"''',
    '''REGISTRY_PATH = ROOT / "config" / "official_company_sources.json"\nCATALOG_PATH = ROOT / "lib" / "catalog-data.ts"\nCOMPANY_REGISTRY_PATH = ROOT / "config" / "company_registry.json"''',
)
replace_once(
    crawler,
    '''def _load_catalog_companies(path: Path = CATALOG_PATH) -> dict[str, dict[str, str]]:\n    """Read the canonical company catalog without maintaining a second slug list."""\n\n    body = path.read_text(encoding="utf-8")\n    section = re.search(\n        r"export\\s+const\\s+companies\\s*:\\s*Company\\[\\]\\s*=\\s*\\[(.*?)\\n\\];",\n        body,\n        flags=re.DOTALL,\n    )\n    if not section:\n        raise ValueError("could not locate the companies array in catalog-data.ts")\n    pattern = re.compile(\n        r'\\{\\s*slug:"([^"]+)",\\s*name:"([^"]+)",'\n        r'(?:\\s*englishName:"[^"]+",)?\\s*region:"([^"]+)",\\s*sector:"([^"]+)"'\n    )\n    companies = {\n        match.group(1): {\n            "name": match.group(2),\n            "region": match.group(3),\n            "sector": match.group(4),\n        }\n        for match in pattern.finditer(section.group(1))\n    }\n    if not companies:\n        raise ValueError("company catalog parser returned no companies")\n    return companies\n\n\ndef load_registry(\n    path: Path = REGISTRY_PATH, catalog_path: Path = CATALOG_PATH\n) -> list[CompanySpec]:''',
    '''def _load_company_registry_json(\n    path: Path = COMPANY_REGISTRY_PATH,\n) -> dict[str, dict[str, str]]:\n    try:\n        payload = json.loads(path.read_text(encoding="utf-8"))\n    except (OSError, json.JSONDecodeError) as exc:\n        raise ValueError(f"could not read company registry JSON: {path}") from exc\n    rows = payload.get("companies", [])\n    if not isinstance(rows, list):\n        raise ValueError("company registry JSON must contain a companies array")\n    companies: dict[str, dict[str, str]] = {}\n    for raw in rows:\n        if not isinstance(raw, dict):\n            continue\n        slug = clean_text(str(raw.get("slug", "")))\n        name = clean_text(str(raw.get("name", "")))\n        region = clean_text(str(raw.get("region", "")))\n        sector = clean_text(str(raw.get("sector", "")))\n        if not slug or not name or not region or not sector:\n            continue\n        if slug in companies:\n            raise ValueError(f"company registry JSON contains duplicate slug: {slug}")\n        companies[slug] = {\n            "name": name,\n            "region": region,\n            "sector": sector,\n        }\n    if not companies:\n        raise ValueError("company registry JSON parser returned no companies")\n    return companies\n\n\ndef _load_catalog_companies(\n    path: Path = CATALOG_PATH,\n    company_registry_path: Path = COMPANY_REGISTRY_PATH,\n) -> dict[str, dict[str, str]]:\n    """Read the canonical company registry without a second slug list.\n\n    Legacy fixtures and older branches may still expose a TypeScript company array.\n    Production now exports companies from ``config/company_registry.json``; when the\n    array is absent, the crawler reads that versioned registry directly.\n    """\n\n    body = path.read_text(encoding="utf-8")\n    section = re.search(\n        r"export\\s+const\\s+companies\\s*:\\s*Company\\[\\]\\s*=\\s*\\[(.*?)\\n\\];",\n        body,\n        flags=re.DOTALL,\n    )\n    if section:\n        pattern = re.compile(\n            r'\\{\\s*slug:"([^"]+)",\\s*name:"([^"]+)",'\n            r'(?:\\s*englishName:"[^"]+",)?\\s*region:"([^"]+)",\\s*sector:"([^"]+)"'\n        )\n        companies = {\n            match.group(1): {\n                "name": match.group(2),\n                "region": match.group(3),\n                "sector": match.group(4),\n            }\n            for match in pattern.finditer(section.group(1))\n        }\n        if companies:\n            return companies\n        raise ValueError("company catalog parser returned no companies")\n    return _load_company_registry_json(company_registry_path)\n\n\ndef load_registry(\n    path: Path = REGISTRY_PATH,\n    catalog_path: Path = CATALOG_PATH,\n    company_registry_path: Path = COMPANY_REGISTRY_PATH,\n) -> list[CompanySpec]:''',
)
replace_once(
    crawler,
    '''    catalog = _load_catalog_companies(catalog_path)''',
    '''    catalog = _load_catalog_companies(catalog_path, company_registry_path)''',
)


test_path = ROOT / "tests" / "test_official_company_registry_dynamic.py"
tests = test_path.read_text(encoding="utf-8")
method = '''    def test_json_registry_fallback_after_typescript_catalog_migration(self) -> None:\n        self.write_registry(self.rows)\n        migrated_catalog = Path(self.tmp.name) / "catalog-migrated.ts"\n        migrated_catalog.write_text(\n            'export { companies } from "./company-registry";\\n',\n            encoding="utf-8",\n        )\n        company_registry = Path(self.tmp.name) / "company_registry.json"\n        company_registry.write_text(\n            json.dumps(\n                {\n                    "schemaVersion": 1,\n                    "companies": [\n                        {\n                            "slug": row["slug"],\n                            "name": row["name"],\n                            "region": row["region"],\n                            "sector": row["sector"],\n                        }\n                        for row in self.rows\n                    ],\n                }\n            ),\n            encoding="utf-8",\n        )\n        specs = load_registry(self.registry, migrated_catalog, company_registry)\n        self.assertEqual([spec.slug for spec in specs], ["alpha", "beta"])\n\n'''
marker = '\n\nif __name__ == "__main__":\n'
if marker not in tests:
    raise SystemExit("dynamic registry test insertion point not found")
if "test_json_registry_fallback_after_typescript_catalog_migration" not in tests:
    test_path.write_text(
        tests.replace(marker, "\n\n" + method + 'if __name__ == "__main__":\n', 1),
        encoding="utf-8",
    )
