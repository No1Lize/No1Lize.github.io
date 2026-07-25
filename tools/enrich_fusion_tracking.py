#!/usr/bin/env python3
"""Promote the user-added controllable-fusion track to a first-class sector.

The migration is deliberately conservative: existing user additions are kept.
Default keywords, people and companies are only inserted when the corresponding
list is empty, so later admin edits are not overwritten on every refresh.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
FUSION_NAME = "可控核聚变"
FUSION_SLUG = "fusion"
FUSION_KEYWORDS = [
    "可控核聚变",
    "聚变能源",
    "托卡马克",
    "高温超导磁体",
    "等离子体约束",
    "聚变净能量增益",
    "氚燃料循环",
]
FUSION_PEOPLE = [
    "杨钊",
    "Bob Mumgaard",
    "David Kirtley",
    "Michl Binderbauer",
]
FUSION_COMPANIES = [
    "能量奇点",
    "Commonwealth Fusion Systems",
    "Helion Energy",
    "TAE Technologies",
    "Zap Energy",
    "General Fusion",
]
ENERGY_FUSION_KEYWORDS = {"可控核聚变", "聚变能源", "托卡马克"}
ENERGY_FUSION_COMPANIES = {
    "能量奇点",
    "Commonwealth Fusion Systems",
    "Helion Energy",
    "TAE Technologies",
    "Zap Energy",
    "General Fusion",
}


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def unique(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean(raw)
        key = value.casefold()
        if not value or key in seen:
            continue
        result.append(value)
        seen.add(key)
    return result


def enrich(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    result = json.loads(json.dumps(payload, ensure_ascii=False))
    tracks = result.setdefault("tracks", [])
    if not isinstance(tracks, list):
        raise ValueError("user tracking tracks must be an array")

    fusion: dict[str, Any] | None = None
    for raw in tracks:
        if not isinstance(raw, dict):
            continue
        if clean(raw.get("name")) == FUSION_NAME or clean(raw.get("slug")) == FUSION_SLUG:
            fusion = raw
            break

    created = fusion is None
    if fusion is None:
        fusion = {
            "slug": FUSION_SLUG,
            "name": FUSION_NAME,
            "enabled": True,
            "custom": False,
            "keywords": [],
            "people": [],
            "sampleCompanies": [],
        }
        tracks.append(fusion)

    fusion["slug"] = FUSION_SLUG
    fusion["name"] = FUSION_NAME
    fusion["custom"] = False
    fusion.setdefault("enabled", True)

    if not isinstance(fusion.get("keywords"), list) or not fusion.get("keywords"):
        fusion["keywords"] = list(FUSION_KEYWORDS)
    else:
        fusion["keywords"] = unique(fusion["keywords"])

    if not isinstance(fusion.get("people"), list) or not fusion.get("people"):
        fusion["people"] = list(FUSION_PEOPLE)
    else:
        fusion["people"] = unique(fusion["people"])

    if not isinstance(fusion.get("sampleCompanies"), list) or not fusion.get("sampleCompanies"):
        fusion["sampleCompanies"] = list(FUSION_COMPANIES)
    else:
        fusion["sampleCompanies"] = unique(fusion["sampleCompanies"])

    energy_changed = False
    for raw in tracks:
        if not isinstance(raw, dict) or clean(raw.get("name")) != "新能源":
            continue
        keywords = raw.get("keywords", [])
        companies = raw.get("sampleCompanies", [])
        if isinstance(keywords, list):
            filtered_keywords = [
                value for value in unique(keywords) if value not in ENERGY_FUSION_KEYWORDS
            ]
            energy_changed = energy_changed or filtered_keywords != keywords
            raw["keywords"] = filtered_keywords
        if isinstance(companies, list):
            filtered_companies = [
                value for value in unique(companies) if value not in ENERGY_FUSION_COMPANIES
            ]
            energy_changed = energy_changed or filtered_companies != companies
            raw["sampleCompanies"] = filtered_companies
        break

    report = {
        "createdFusionTrack": created,
        "fusionSlug": fusion["slug"],
        "fusionKeywords": len(fusion["keywords"]),
        "fusionPeople": len(fusion["people"]),
        "fusionCompanies": len(fusion["sampleCompanies"]),
        "removedFusionFromEnergy": energy_changed,
    }
    return result, report


def main() -> int:
    if not TRACKING_PATH.exists():
        raise SystemExit(f"missing tracking config: {TRACKING_PATH}")
    payload = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("user tracking configuration must be a JSON object")
    enriched, report = enrich(payload)
    if enriched != payload:
        TRACKING_PATH.write_text(
            json.dumps(enriched, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
