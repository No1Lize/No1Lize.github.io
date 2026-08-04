"""Validate and aggregate manual source-quality review samples."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_PATH = ROOT / "config" / "source_quality_reviews.json"


def _integer(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _valid_iso(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
        return True
    except ValueError:
        return False


def load_review_manifest(path: Path = DEFAULT_REVIEW_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source quality review manifest must be an object")
    if int(payload.get("schemaVersion", 0)) != 1:
        raise ValueError("unsupported source quality review schema")
    reviews = payload.get("reviews", [])
    if not isinstance(reviews, list):
        raise ValueError("source quality reviews must be an array")

    seen: set[tuple[str, str]] = set()
    for index, raw in enumerate(reviews):
        if not isinstance(raw, dict):
            raise ValueError(f"review {index} must be an object")
        source_id = str(raw.get("sourceId") or "").strip()
        period = str(raw.get("period") or "").strip()
        reviewer = str(raw.get("reviewer") or "").strip()
        reviewed_at = raw.get("reviewedAt")
        reviewed = _integer(raw.get("reviewedRecords"))
        misattributed = _integer(raw.get("misattributedRecords"))
        duplicates = _integer(raw.get("confirmedDuplicateRecords", 0))
        if not source_id:
            raise ValueError(f"review {index} is missing sourceId")
        if len(period) != 7 or period[4] != "-":
            raise ValueError(f"review {index} has invalid period")
        if not reviewer:
            raise ValueError(f"review {index} is missing reviewer")
        if not _valid_iso(reviewed_at):
            raise ValueError(f"review {index} has invalid reviewedAt")
        if reviewed < 1:
            raise ValueError(f"review {index} must review at least one record")
        if misattributed < 0 or misattributed > reviewed:
            raise ValueError(f"review {index} has invalid misattributedRecords")
        if duplicates < 0 or duplicates > reviewed:
            raise ValueError(f"review {index} has invalid confirmedDuplicateRecords")
        key = (source_id, period)
        if key in seen:
            raise ValueError(f"duplicate review for {source_id} in {period}")
        seen.add(key)
    return payload


def review_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for raw in payload.get("reviews", []):
        if not isinstance(raw, dict):
            continue
        source_id = str(raw.get("sourceId") or "").strip()
        if not source_id:
            continue
        current = result.setdefault(
            source_id,
            {
                "reviewedRecords": 0,
                "misattributedRecords": 0,
                "confirmedDuplicateRecords": 0,
                "lastReviewedAt": None,
                "reviewer": None,
                "period": None,
                "notes": [],
            },
        )
        current["reviewedRecords"] += int(raw.get("reviewedRecords", 0) or 0)
        current["misattributedRecords"] += int(
            raw.get("misattributedRecords", 0) or 0
        )
        current["confirmedDuplicateRecords"] += int(
            raw.get("confirmedDuplicateRecords", 0) or 0
        )
        reviewed_at = str(raw.get("reviewedAt") or "")
        if not current["lastReviewedAt"] or reviewed_at > current["lastReviewedAt"]:
            current["lastReviewedAt"] = reviewed_at
            current["reviewer"] = str(raw.get("reviewer") or "")
            current["period"] = str(raw.get("period") or "")
        note = str(raw.get("notes") or "").strip()
        if note:
            current["notes"].append(note)

    for item in result.values():
        reviewed = item["reviewedRecords"]
        item["misattributionRate"] = (
            round(item["misattributedRecords"] / reviewed, 4) if reviewed else None
        )
        item["confirmedDuplicateRate"] = (
            round(item["confirmedDuplicateRecords"] / reviewed, 4)
            if reviewed
            else None
        )
    return result
