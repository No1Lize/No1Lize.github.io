"""Publication quarantine helpers for persistently unhealthy public sources.

Sources continue to be probed by the full refresh so recovery can be measured and
full-source audit coverage remains intact. While a source is quarantined or in
probation, newly crawled rows are withheld from publication and the last verified
snapshot remains visible. Three productive probes restore publication by default.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_PATH = ROOT / "public" / "data" / "source_health.json"
DEFAULT_POLICY_PATH = ROOT / "config" / "source_health_policy.json"


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return fallback


def publication_quarantine_ids(
    state: dict[str, Any],
    policy: dict[str, Any],
) -> set[str]:
    allowed_grades = {
        str(value)
        for value in policy.get("quarantineGrades", ["C", "D"])
        if str(value) in {"A", "B", "C", "D"}
    }
    sources = state.get("sources", {})
    if not isinstance(sources, dict):
        return set()
    return {
        source_id
        for source_id, entry in sources.items()
        if isinstance(entry, dict)
        and str(entry.get("evidenceGrade") or "D") in allowed_grades
        and str(entry.get("collectionState") or "active")
        in {"quarantined", "probation"}
    }


def load_publication_quarantine(
    state_path: Path = DEFAULT_STATE_PATH,
    policy_path: Path = DEFAULT_POLICY_PATH,
) -> set[str]:
    state = _read_json(state_path, {})
    policy = _read_json(policy_path, {})
    return publication_quarantine_ids(
        state if isinstance(state, dict) else {},
        policy if isinstance(policy, dict) else {},
    )


def withhold_quarantined_publication(
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    quarantined_ids: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Filter rows/statuses passed to batch replacement while retaining probe status.

    The caller keeps the original status list in the public status ledger. Only the
    status list used to decide which historical source batches are replaced is
    filtered, so quarantined sources retain their last verified published rows.
    """

    if not quarantined_ids:
        return incoming, statuses

    for status in statuses:
        source_id = str(status.get("id") or status.get("sourceId") or "")
        if source_id in quarantined_ids:
            status["publicationWithheld"] = True
            status["collectionState"] = "probation"

    publishable = [
        article
        for article in incoming
        if str(article.get("sourceId") or "") not in quarantined_ids
    ]
    replacement_statuses = [
        status
        for status in statuses
        if str(status.get("id") or status.get("sourceId") or "")
        not in quarantined_ids
    ]
    return publishable, replacement_statuses
