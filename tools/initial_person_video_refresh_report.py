#!/usr/bin/env python3
"""Write a compact report for the initial public person-video refresh."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PEOPLE_PATH = ROOT / "public" / "data" / "people.json"
REPORT_PATH = ROOT / "diagnostics" / "person-video-refresh.json"


def platform_for(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold()
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "bilibili.com" in host:
        return "bilibili"
    if "channels.weixin.qq.com" in host or "weixin.qq.com" in host:
        return "wechatChannels"
    return ""


def main() -> int:
    payload = json.loads(PEOPLE_PATH.read_text(encoding="utf-8"))
    counts = {"youtube": 0, "bilibili": 0, "wechatChannels": 0}
    people: list[dict[str, object]] = []
    samples: list[dict[str, str]] = []
    for person in payload.get("people") or []:
        found: list[str] = []
        for item in person.get("speeches") or []:
            url = str(item.get("url") or "")
            platform = platform_for(url)
            if not platform:
                continue
            counts[platform] += 1
            found.append(platform)
            if len(samples) < 16:
                samples.append({
                    "person": str(person.get("name") or ""),
                    "platform": platform,
                    "title": str(item.get("title") or ""),
                    "url": url,
                })
        if found:
            people.append({
                "name": str(person.get("name") or ""),
                "platforms": sorted(set(found)),
            })
    result = {
        "generatedAt": payload.get("generatedAt"),
        "personCount": payload.get("personCount"),
        "peopleWithVideo": len(people),
        "platformCounts": counts,
        "people": people,
        "samples": samples,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
