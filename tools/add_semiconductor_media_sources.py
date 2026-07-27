#!/usr/bin/env python3
"""Upsert professional semiconductor media sources into user tracking config."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"

SEMICONDUCTOR_MEDIA_SOURCES: tuple[dict[str, Any], ...] = (
    {
        "id": "source-semiconductor-technology-sohu",
        "name": "半导体技术",
        "url": "https://m.sohu.com/media/120498874",
        "sourceType": "listing-search",
        "sourceCategory": "media",
        "region": "中国",
        "sector": "半导体",
        "company": "",
        "ticker": "",
        "keywords": [
            "半导体",
            "芯片",
            "集成电路",
            "晶圆",
            "封装测试",
            "可靠性测试",
            "失效分析",
            "半导体设备",
        ],
        "enabled": True,
    },
    {
        "id": "source-chiptrend-ic-sohu",
        "name": "芯潮IC",
        "url": "https://mp.sohu.com/profile?xpt=MzlkZjljNGItNzVjMS00MGRiLWJlYjctMGVlMTYzZjkyOTcy",
        "sourceType": "listing-search",
        "sourceCategory": "media",
        "region": "中国",
        "sector": "半导体",
        "company": "",
        "ticker": "",
        "keywords": [
            "半导体",
            "芯片",
            "集成电路",
            "晶圆厂",
            "封装",
            "半导体设备",
            "半导体材料",
            "融资",
            "IPO",
        ],
        "enabled": True,
    },
    {
        "id": "source-eefocus-semiconductor",
        "name": "与非网 EEFocus",
        "url": "https://www.eefocus.com/tag/%E5%8D%8A%E5%AF%BC%E4%BD%93%E4%BA%A7%E4%B8%9A/article/",
        "sourceType": "listing-search",
        "sourceCategory": "media",
        "region": "中国",
        "sector": "半导体",
        "company": "",
        "ticker": "",
        "keywords": [
            "半导体",
            "芯片",
            "集成电路",
            "AI芯片",
            "EDA",
            "晶圆",
            "先进封装",
            "功率半导体",
            "产业研究",
        ],
        "enabled": True,
    },
)


def upsert_sources(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    sources = payload.get("sources")
    if not isinstance(sources, list):
        raise ValueError("tracking sources must be an array")

    by_id = {
        str(source.get("id")): index
        for index, source in enumerate(sources)
        if isinstance(source, dict) and source.get("id")
    }
    changed = False
    for expected in SEMICONDUCTOR_MEDIA_SOURCES:
        source_id = str(expected["id"])
        replacement = dict(expected)
        if source_id in by_id:
            index = by_id[source_id]
            if sources[index] != replacement:
                sources[index] = replacement
                changed = True
        else:
            sources.append(replacement)
            by_id[source_id] = len(sources) - 1
            changed = True

    next_payload = dict(payload)
    next_payload["sources"] = sources
    return next_payload, changed


def main() -> int:
    payload = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    next_payload, changed = upsert_sources(payload)
    if not changed:
        print("Semiconductor media sources already registered.")
        return 0
    TRACKING_PATH.write_text(
        json.dumps(next_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Registered semiconductor media sources: "
        + ", ".join(source["name"] for source in SEMICONDUCTOR_MEDIA_SOURCES)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
