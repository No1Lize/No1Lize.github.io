#!/usr/bin/env python3
"""Validate that a committed snapshot came from one complete crawler run."""

from __future__ import annotations

import json
from pathlib import Path

try:
    from . import crawl_articles
    from . import crawl_official_companies
except ImportError:
    import crawl_articles
    import crawl_official_companies

ROOT = Path(__file__).resolve().parents[1]
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"


def _enabled_ids(rows: object) -> set[str]:
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("id"))
        for row in rows
        if isinstance(row, dict)
        and row.get("id")
        and row.get("enabled", True) is not False
    }


def main() -> int:
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    audit = payload.get("refreshAudit")
    statuses = [item for item in payload.get("sourceStatus", []) if isinstance(item, dict)]
    errors: list[str] = []

    if not isinstance(audit, dict):
        errors.append("missing refreshAudit")
        audit = {}
    if audit.get("mode") != "full" or audit.get("pipelineCompleted") is not True:
        errors.append("snapshot was not finalized by the full refresh pipeline")

    completed_at = str(audit.get("completedAt") or "")
    if not completed_at:
        errors.append("missing refresh completion timestamp")

    status_ids = [str(item.get("id") or "") for item in statuses]
    status_id_set = {value for value in status_ids if value}
    if len(status_id_set) != len([value for value in status_ids if value]):
        errors.append("duplicate source status ids")
    if not statuses:
        errors.append("source status ledger is empty")
    if completed_at and any(item.get("lastAttemptAt") != completed_at for item in statuses):
        errors.append("source status ledger contains stale rows")

    config = crawl_articles.load_config()
    expected_core = {source.id for source in crawl_articles.NEWS_SOURCES}
    expected_core.update(_enabled_ids(config.get("feeds")))
    expected_core.update(_enabled_ids(config.get("xProfiles")))
    expected_core.update(_enabled_ids(config.get("papers")))
    expected_core.update(_enabled_ids(config.get("publicDiscovery")))

    official_specs = crawl_official_companies.load_registry()
    expected_official = {spec.source_id for spec in official_specs}

    missing_core = sorted(expected_core - status_id_set)
    missing_official = sorted(expected_official - status_id_set)
    if missing_core:
        errors.append(f"missing core source statuses: {', '.join(missing_core)}")
    if missing_official:
        errors.append(
            "missing official company statuses: " + ", ".join(missing_official)
        )

    quality_gate = payload.get("qualityGate")
    if not isinstance(quality_gate, dict) or quality_gate.get("passed") is not True:
        errors.append("quality gate did not pass")

    coverage = payload.get("trackCoverage")
    if not isinstance(coverage, dict) or not coverage:
        errors.append("tracking coverage is missing")
    else:
        incomplete_tracks = sorted(
            slug
            for slug, row in coverage.items()
            if not isinstance(row, dict)
            or int(row.get("completedSources", 0) or 0)
            < int(row.get("expectedSources", 0) or 0)
        )
        if incomplete_tracks:
            errors.append("incomplete track coverage: " + ", ".join(incomplete_tracks))

    summary = {
        "sourceStatuses": len(statuses),
        "expectedCoreSources": len(expected_core),
        "expectedOfficialCompanies": len(expected_official),
        "latestPublishedAt": audit.get("latestPublishedAt"),
        "todayArticleCount": audit.get("todayArticleCount"),
        "todaySourceCount": audit.get("todaySourceCount"),
        "errors": errors,
    }
    print(json.dumps(summary, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
