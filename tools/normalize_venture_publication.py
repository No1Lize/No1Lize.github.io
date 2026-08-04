#!/usr/bin/env python3
"""Normalize venture profiles while preserving terminal-owned publication fields."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

try:
    from .crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH
    from .enforce_venture_entity_semantics import _exit_performance
    from .finalize_venture_profiles import _capital_summary, finalize_team
    from .normalize_venture_profiles import normalize_payload
    from .venture_profile_extraction import evidence_score, parse_catalog
except ImportError:
    from crawl_venture_profiles import CATALOG_PATH, OUTPUT_PATH
    from enforce_venture_entity_semantics import _exit_performance
    from finalize_venture_profiles import _capital_summary, finalize_team
    from normalize_venture_profiles import normalize_payload
    from venture_profile_extraction import evidence_score, parse_catalog


def normalize_publication_payload(
    payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply base normalization without competing with terminal field owners.

    The base normalizer owns product/event list consistency. The terminal
    structural and entity-semantic gates own the full team schema and the
    derived capital/exit summaries. Rebuilding those terminal-owned fields from
    the pre-normalization snapshot prevents deterministic gates from rewriting
    one another indefinitely.
    """
    original = copy.deepcopy(payload)
    normalized, base_stats = normalize_payload(copy.deepcopy(payload), catalog_text)
    company_specs, institution_specs = parse_catalog(catalog_text)
    company_by_slug = {item.slug: item for item in company_specs}
    institution_by_slug = {item.slug: item for item in institution_specs}

    restored_company_teams = 0
    restored_institution_teams = 0
    refreshed_capital_summaries = 0
    refreshed_exit_summaries = 0

    original_companies = (
        original.get("companies", {}) if isinstance(original.get("companies"), dict) else {}
    )
    normalized_companies = (
        normalized.get("companies", {}) if isinstance(normalized.get("companies"), dict) else {}
    )
    for slug, profile in normalized_companies.items():
        if not isinstance(profile, dict):
            continue
        spec = company_by_slug.get(slug)
        aliases = spec.aliases if spec else (profile.get("name", ""),)
        original_profile = original_companies.get(slug, {})
        original_team = (
            original_profile.get("team", [])
            if isinstance(original_profile, dict)
            and isinstance(original_profile.get("team"), list)
            else profile.get("team", [])
        )
        terminal_team = finalize_team(original_team, aliases)
        if terminal_team != profile.get("team", []):
            restored_company_teams += 1
        profile["team"] = terminal_team

        capital_summary = _capital_summary(
            profile.get("financing", []) if isinstance(profile.get("financing"), list) else []
        )
        if capital_summary != profile.get("capitalSummary"):
            refreshed_capital_summaries += 1
        profile["capitalSummary"] = capital_summary

        exit_summary = _exit_performance(
            profile.get("capitalMarkets", [])
            if isinstance(profile.get("capitalMarkets"), list)
            else [],
            listed=bool(spec and spec.status == "已上市"),
        )
        if exit_summary != profile.get("exitPerformance"):
            refreshed_exit_summaries += 1
        profile["exitPerformance"] = exit_summary
        profile["evidenceScore"] = evidence_score(profile, "company")

    original_institutions = (
        original.get("institutions", {})
        if isinstance(original.get("institutions"), dict)
        else {}
    )
    normalized_institutions = (
        normalized.get("institutions", {})
        if isinstance(normalized.get("institutions"), dict)
        else {}
    )
    for slug, profile in normalized_institutions.items():
        if not isinstance(profile, dict):
            continue
        spec = institution_by_slug.get(slug)
        aliases = spec.aliases if spec else (profile.get("name", ""),)
        original_profile = original_institutions.get(slug, {})
        original_team = (
            original_profile.get("team", [])
            if isinstance(original_profile, dict)
            and isinstance(original_profile.get("team"), list)
            else profile.get("team", [])
        )
        terminal_team = finalize_team(original_team, aliases)
        if terminal_team != profile.get("team", []):
            restored_institution_teams += 1
        profile["team"] = terminal_team
        profile["evidenceScore"] = evidence_score(profile, "institution")

    diagnostics = {
        "base": base_stats,
        "restoredCompanyTeams": restored_company_teams,
        "restoredInstitutionTeams": restored_institution_teams,
        "refreshedCapitalSummaries": refreshed_capital_summaries,
        "refreshedExitSummaries": refreshed_exit_summaries,
    }
    return normalized, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    normalized, diagnostics = normalize_publication_payload(
        payload, args.catalog.read_text(encoding="utf-8")
    )
    rendered = json.dumps(normalized, ensure_ascii=False, indent=2) + "\n"
    current = args.input.read_text(encoding="utf-8")
    unchanged = rendered == current
    quality_passed = bool(normalized.get("qualityGate", {}).get("passed", False))
    print(
        json.dumps(
            {
                "changed": not unchanged,
                "qualityPassed": quality_passed,
                "diagnostics": diagnostics,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )

    if args.check:
        if not unchanged:
            print("Venture profile snapshot requires publication-aware normalization.")
            return 1
        return 0 if quality_passed else 1

    if not unchanged:
        args.input.write_text(rendered, encoding="utf-8")
        print(f"Updated {args.input}.")
    return 0 if quality_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
