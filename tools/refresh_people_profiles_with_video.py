#!/usr/bin/env python3
"""Run the person profile refresh with public video-platform enrichment enabled."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import refresh_people_profiles as core
from tools.person_video_discovery import discover_person_video_materials
from tools.wechat_channel_card_discovery import discover_embedded_wechat_video_materials

_BASE_ENRICH_CANDIDATE = core.enrich_candidate


def merge_video_materials(profile: dict[str, Any], video_materials: list[dict[str, str]]) -> dict[str, Any]:
    if not video_materials:
        return profile
    materials = core.dedupe_materials([*video_materials, *(profile.get("materials") or [])])
    speeches = [item for item in materials if item.get("type") in {"speech", "interview", "qa"}]
    sources = core.unique([
        *(profile.get("sources") or []),
        *(str(item.get("url") or "") for item in video_materials),
    ])
    status = (
        "complete"
        if profile.get("background") and len(materials) >= 4
        else "partial"
        if materials
        else "pending"
    )
    return {
        **profile,
        "materials": materials,
        "speeches": speeches,
        "sources": sources,
        "status": status,
    }


def enrich_candidate(
    candidate: dict[str, Any],
    previous: dict[str, Any] | None,
    articles: list[dict[str, Any]],
    offline: bool,
) -> dict[str, Any]:
    profile = _BASE_ENRICH_CANDIDATE(candidate, previous, articles, offline)
    if offline:
        return profile
    video_materials: list[dict[str, str]] = []
    try:
        video_materials.extend(discover_person_video_materials(candidate))
    except Exception:
        pass
    if articles:
        try:
            video_materials.extend(
                discover_embedded_wechat_video_materials(candidate, articles)
            )
        except Exception:
            pass
    return merge_video_materials(profile, video_materials)


# The core builder resolves this global from its own module, so replace it once before
# exposing the ordinary CLI/build entry points.
core.enrich_candidate = enrich_candidate
build_payload = core.build_payload
main = core.main


if __name__ == "__main__":
    raise SystemExit(main())
