#!/usr/bin/env python3
"""Load stable company research sources already maintained by the repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def load_official_websites(root: Path) -> dict[str, str]:
    """Return listed-company slug -> best public homepage/IR URL."""

    payload = _read_json(root / "config" / "official_company_sources.json", {})
    companies = payload.get("companies") if isinstance(payload, dict) else []
    result: dict[str, str] = {}
    for company in companies if isinstance(companies, list) else []:
        if not isinstance(company, dict):
            continue
        slug = str(company.get("slug") or "").strip()
        homepage = str(company.get("homepage") or "").strip()
        news_urls = company.get("newsUrls") if isinstance(company.get("newsUrls"), list) else []
        preferred = next(
            (
                str(url).strip()
                for url in news_urls
                if str(url).startswith(("http://", "https://"))
                and any(token in str(url).casefold() for token in ("investor", "investors", "ir."))
            ),
            "",
        )
        url = preferred or homepage
        if slug and url.startswith(("http://", "https://")):
            result[slug] = url
    return result


def load_local_cik_map(root: Path) -> dict[str, str]:
    """Return ticker -> zero-padded CIK from the existing article snapshot."""

    payload = _read_json(root / "public" / "data" / "articles.json", {})
    facts = payload.get("companyFacts") if isinstance(payload, dict) else {}
    result: dict[str, str] = {}
    for fact in facts.values() if isinstance(facts, dict) else []:
        if not isinstance(fact, dict):
            continue
        ticker = str(fact.get("ticker") or "").strip().upper()
        cik_raw = "".join(character for character in str(fact.get("cik") or "") if character.isdigit())
        if ticker and cik_raw:
            result[ticker] = cik_raw.zfill(10)
    return result


def merge_source_maps(primary: dict[str, str], fallback: dict[str, str]) -> dict[str, str]:
    """Keep explicit primary values while filling missing keys from fallback."""

    return {**fallback, **{key: value for key, value in primary.items() if value}}
