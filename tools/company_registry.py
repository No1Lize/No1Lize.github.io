#!/usr/bin/env python3
"""Maintain the machine-readable company registry used by startup pages.

The repository historically stored companies as one-line TypeScript object literals in
``lib/catalog-data.ts``.  This module migrates those rows to
``config/company_registry.json`` and validates future onboarding changes.  The
TypeScript catalog keeps institutions and reports, while companies are loaded from the
versioned JSON registry.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
REGISTRY_PATH = ROOT / "config" / "company_registry.json"
COMPANY_EXPORT_MARKER = 'export const companies: Company[] = ['
COMPANY_END_MARKER = '\n\nexport type Institution'
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def clean(value: Any, limit: int = 2_000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def unique(values: Iterable[Any], limit: int = 50) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean(value, 500)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def public_http_url(value: Any) -> str:
    text = clean(value, 2_000)
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    return text if parsed.scheme in {"http", "https"} and parsed.netloc else ""


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(fallback)


def _string_field(line: str, key: str) -> str:
    match = re.search(rf'\b{re.escape(key)}:"([^\"]*)"', line)
    return clean(match.group(1), 2_000) if match else ""


def _number_field(line: str, key: str, fallback: float = 0.0) -> float:
    match = re.search(rf"\b{re.escape(key)}:([0-9]+(?:\.[0-9]+)?)", line)
    return float(match.group(1)) if match else fallback


def _source_field(line: str) -> dict[str, str]:
    match = re.search(r'source:official\("([^\"]+)","([^\"]+)"\)', line)
    if not match:
        return {"name": "", "url": "", "level": "官方披露"}
    return {
        "name": clean(match.group(1), 240),
        "url": public_http_url(match.group(2)),
        "level": "官方披露",
    }


def parse_catalog_companies(text: str) -> list[dict[str, Any]]:
    start = text.find(COMPANY_EXPORT_MARKER)
    if start < 0:
        return []
    end = text.find(COMPANY_END_MARKER, start)
    block = text[start : end if end >= 0 else len(text)]
    companies: list[dict[str, Any]] = []
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line.startswith("{ slug:"):
            continue
        source = _source_field(line)
        slug = _string_field(line, "slug")
        name = _string_field(line, "name")
        if not slug or not name or not source["url"]:
            continue
        entry: dict[str, Any] = {
            "slug": slug,
            "name": name,
            "englishName": _string_field(line, "englishName"),
            "region": _string_field(line, "region"),
            "sector": _string_field(line, "sector"),
            "stage": _string_field(line, "stage"),
            "status": _string_field(line, "status"),
            "founded": _string_field(line, "founded"),
            "headquarters": _string_field(line, "headquarters"),
            "summary": _string_field(line, "summary"),
            "product": _string_field(line, "product"),
            "source": source,
            "confidence": _number_field(line, "confidence", 0.9),
            "aliases": unique([name, _string_field(line, "englishName")]),
            "registrySource": "legacy-catalog-migration",
        }
        companies.append(normalize_company(entry))
    return companies


def normalize_company(value: Any) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    source = row.get("source") if isinstance(row.get("source"), dict) else {}
    status = clean(row.get("status"), 40) or "运营中"
    if status not in {"运营中", "已上市"}:
        status = "运营中"
    confidence = max(0.5, min(1.0, float(row.get("confidence", 0.9) or 0.9)))
    name = clean(row.get("name"), 240)
    english_name = clean(row.get("englishName"), 240)
    normalized = {
        "slug": clean(row.get("slug"), 120).casefold(),
        "name": name,
        "englishName": english_name,
        "region": clean(row.get("region"), 80) or "全球",
        "sector": clean(row.get("sector"), 120) or "待分类",
        "stage": clean(row.get("stage"), 80) or "待补充",
        "status": status,
        "founded": clean(row.get("founded"), 40),
        "headquarters": clean(row.get("headquarters"), 160),
        "summary": clean(row.get("summary"), 1_200),
        "product": clean(row.get("product"), 1_200),
        "source": {
            "name": clean(source.get("name"), 240) or name,
            "url": public_http_url(source.get("url")),
            "level": clean(source.get("level"), 80) or "官方披露",
        },
        "confidence": round(confidence, 2),
        "aliases": unique([name, english_name, *(row.get("aliases") or [])], 30),
        "registrySource": clean(row.get("registrySource"), 120) or "manual",
    }
    onboarding = row.get("onboarding") if isinstance(row.get("onboarding"), dict) else {}
    if onboarding:
        normalized["onboarding"] = {
            "candidateKey": clean(onboarding.get("candidateKey"), 160),
            "reviewedBy": clean(onboarding.get("reviewedBy"), 120),
            "decidedAt": clean(onboarding.get("decidedAt"), 80),
            "publishedAt": clean(onboarding.get("publishedAt"), 80),
            "evidenceFingerprint": clean(onboarding.get("evidenceFingerprint"), 10_000),
        }
    return normalized


def normalize_registry(value: Any) -> dict[str, Any]:
    payload = value if isinstance(value, dict) else {}
    rows = payload.get("companies") if isinstance(payload.get("companies"), list) else []
    companies = [normalize_company(row) for row in rows if isinstance(row, dict)]
    companies.sort(key=lambda row: (row["slug"], row["name"].casefold()))
    return {
        "schemaVersion": max(1, int(payload.get("schemaVersion", 1) or 1)),
        "generatedAt": clean(payload.get("generatedAt"), 80),
        "companies": companies,
    }


def validate_registry(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    seen_slugs: set[str] = set()
    seen_names: dict[str, str] = {}
    for index, company in enumerate(payload.get("companies", [])):
        slug = clean(company.get("slug"), 120)
        name = clean(company.get("name"), 240)
        prefix = f"company {index} ({slug or name or 'unknown'})"
        if not SLUG_RE.fullmatch(slug):
            errors.append(f"{prefix}: invalid slug")
        elif slug in seen_slugs:
            errors.append(f"{prefix}: duplicate slug")
        seen_slugs.add(slug)
        if not name:
            errors.append(f"{prefix}: missing name")
        name_key = name.casefold()
        if name_key and name_key in seen_names and seen_names[name_key] != slug:
            errors.append(f"{prefix}: duplicate canonical name with {seen_names[name_key]}")
        elif name_key:
            seen_names[name_key] = slug
        if not clean(company.get("region"), 80):
            errors.append(f"{prefix}: missing region")
        if not clean(company.get("sector"), 120):
            errors.append(f"{prefix}: missing sector")
        if not clean(company.get("stage"), 80):
            errors.append(f"{prefix}: missing stage")
        if company.get("status") not in {"运营中", "已上市"}:
            errors.append(f"{prefix}: invalid status")
        if len(clean(company.get("summary"), 1_200)) < 12:
            errors.append(f"{prefix}: summary too short")
        if len(clean(company.get("product"), 1_200)) < 4:
            errors.append(f"{prefix}: product too short")
        source = company.get("source") if isinstance(company.get("source"), dict) else {}
        if not public_http_url(source.get("url")):
            errors.append(f"{prefix}: invalid official source URL")
        confidence = float(company.get("confidence", 0) or 0)
        if not 0.5 <= confidence <= 1:
            errors.append(f"{prefix}: confidence outside 0.5-1")
    return errors


def write_registry(path: Path, payload: dict[str, Any]) -> bool:
    normalized = normalize_registry(payload)
    normalized["generatedAt"] = datetime.now(UTC).replace(microsecond=0).isoformat()
    previous = normalize_registry(load_json(path, {}))
    comparable_previous = {**previous, "generatedAt": ""}
    comparable_next = {**normalized, "generatedAt": ""}
    if comparable_previous == comparable_next and path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return True


def migrate_catalog(catalog_path: Path = CATALOG_PATH, registry_path: Path = REGISTRY_PATH) -> dict[str, Any]:
    catalog_text = catalog_path.read_text(encoding="utf-8")
    extracted = parse_catalog_companies(catalog_text)
    current = normalize_registry(load_json(registry_path, {}))
    if extracted:
        by_slug = {row["slug"]: row for row in current["companies"]}
        for row in extracted:
            by_slug.setdefault(row["slug"], row)
        current["companies"] = list(by_slug.values())
    errors = validate_registry(normalize_registry(current))
    if errors:
        raise ValueError("; ".join(errors[:20]))
    registry_changed = write_registry(registry_path, current)

    catalog_changed = False
    if COMPANY_EXPORT_MARKER in catalog_text:
        start = catalog_text.index(COMPANY_EXPORT_MARKER)
        end = catalog_text.index(COMPANY_END_MARKER, start)
        replacement = 'export { companies } from "./company-registry";'
        catalog_text = catalog_text[:start] + replacement + catalog_text[end:]
        catalog_text = catalog_text.replace(
            '  region: "中国" | "美国";',
            '  region: string;',
            1,
        )
        catalog_path.write_text(catalog_text, encoding="utf-8")
        catalog_changed = True

    return {
        "companyCount": len(normalize_registry(load_json(registry_path, {}))["companies"]),
        "registryChanged": registry_changed,
        "catalogChanged": catalog_changed,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--migrate-catalog", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.migrate_catalog:
        result = migrate_catalog(args.catalog, args.registry)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0

    payload = normalize_registry(load_json(args.registry, {}))
    errors = validate_registry(payload)
    print(
        json.dumps(
            {
                "valid": not errors,
                "companyCount": len(payload["companies"]),
                "errors": errors,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
