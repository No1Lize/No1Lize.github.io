#!/usr/bin/env python3
"""Register verified public communities and media columns for sample-company teams.

The existing sample-company people pass identifies founders and core executives and
adds verified X handles plus several social-profile URLs. This complementary pass
looks only at already sourced local person records and registers additional exact
public entries such as WeChat materials, Zhihu profiles, Jike profiles, Medium or
Substack pages, personal blogs, and author/column pages on recognized media sites.

No account is guessed. No login-only page, private endpoint, credential, or inferred
URL is used. A source is added only when an exact public URL already exists in the
repository's people snapshot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.enrich_tracking_people_from_sample_companies import (  # noqa: E402
    CONFIG_PATH,
    LEDGER_PATH,
    PEOPLE_PATH,
    VENTURE_PROFILES_PATH,
    add_ledger_entry,
    blocked_values,
    choose_core_team,
    clean_text,
    company_keys,
    empty_ledger,
    load_json,
    normalized_key,
    now_iso,
    person_name_key,
    profile_index,
    slugify,
    sync_tombstones,
)

MAX_PEOPLE_PER_TRACK = 8
MAX_CHANNELS_PER_PERSON = 5
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "spm",
}

MEDIA_COLUMN_HOSTS = {
    "36kr.com",
    "caixin.com",
    "cnstock.com",
    "forbes.com",
    "ft.com",
    "ftchinese.com",
    "huxiu.com",
    "pedaily.cn",
    "reuters.com",
    "sina.com.cn",
    "stcn.com",
    "techcrunch.com",
    "theinformation.com",
    "tmtpost.com",
    "venturebeat.com",
    "wallstreetcn.com",
    "yahoo.com",
    "yicai.com",
}
MEDIA_COLUMN_PATH = re.compile(
    r"/(?:author|authors|column|columns|contributors?|people|profile|profiles|writer|writers|u)/",
    re.IGNORECASE,
)
EXPLICIT_PROFILE_TYPES = {
    "author_profile",
    "blog",
    "column",
    "newsletter",
    "official_profile",
    "personal_site",
    "profile",
    "public_profile",
    "social_profile",
}
SKIPPED_HOSTS = {
    "en.wikipedia.org",
    "zh.wikipedia.org",
    "www.wikidata.org",
    "wikidata.org",
}


@dataclass(frozen=True)
class PublicChannel:
    platform: str
    url: str
    priority: int


def normalize_url(value: Any) -> str:
    raw = clean_text(value, 800)
    if not raw:
        return ""
    try:
        parts = urlsplit(raw)
    except ValueError:
        return ""
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        return ""
    query = urlencode(
        [
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_QUERY_KEYS
        ]
    )
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, query, ""))


def base_host(host: str) -> str:
    value = host.lower().removeprefix("www.")
    for candidate in sorted(MEDIA_COLUMN_HOSTS, key=len, reverse=True):
        if value == candidate or value.endswith(f".{candidate}"):
            return candidate
    return value


def classify_public_channel(value: Any, metadata: dict[str, Any] | None = None) -> PublicChannel | None:
    url = normalize_url(value)
    if not url:
        return None
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path or "/"
    lower_path = path.lower()
    if host in SKIPPED_HOSTS:
        return None

    if host == "mp.weixin.qq.com" and (
        lower_path.startswith("/s") or lower_path.startswith("/mp/profile_ext")
    ):
        return PublicChannel("微信公开材料", url, 100)
    if host == "zhihu.com" and re.match(r"^/(?:people|org|column)/[^/]+", lower_path):
        return PublicChannel("知乎", url, 95)
    if host == "okjike.com" and re.match(r"^/users/[^/]+", lower_path):
        return PublicChannel("即刻", url, 94)
    if host == "xiaohongshu.com" and lower_path.startswith("/user/profile/"):
        return PublicChannel("小红书", url, 92)
    if host == "medium.com" and lower_path.startswith("/@"):
        return PublicChannel("Medium", url, 90)
    if host.endswith(".medium.com") and host != "www.medium.com":
        return PublicChannel("Medium", url, 89)
    if host.endswith(".substack.com") or (
        host == "substack.com" and re.match(r"^/@[^/]+", lower_path)
    ):
        return PublicChannel("Substack", url, 88)

    root_host = base_host(host)
    if root_host in MEDIA_COLUMN_HOSTS and MEDIA_COLUMN_PATH.search(lower_path):
        return PublicChannel("媒体专栏", url, 85)

    item = metadata or {}
    item_type = clean_text(item.get("type"), 80).lower()
    platform_hint = " ".join(
        clean_text(item.get(field), 120).lower()
        for field in ("platform", "source", "title", "name")
    )
    if item_type in EXPLICIT_PROFILE_TYPES or re.search(
        r"个人主页|个人网站|博客|专栏|作者页|newsletter|personal site|author profile|column|blog",
        platform_hint,
        re.IGNORECASE,
    ):
        return PublicChannel("个人主页 / 媒体专栏", url, 75)
    return None


def iter_person_urls(person: dict[str, Any]) -> Iterable[tuple[str, dict[str, Any]]]:
    for field in (
        "homepage",
        "website",
        "blogUrl",
        "columnUrl",
        "wechatUrl",
        "newsletterUrl",
    ):
        value = person.get(field)
        if isinstance(value, str) and value.strip():
            yield value, {"type": field, "title": field}

    for handle in person.get("handles") or []:
        if isinstance(handle, dict):
            url = handle.get("url")
            if isinstance(url, str) and url.strip():
                yield url, handle

    for field in ("socialAccounts", "materials", "speeches"):
        for item in person.get(field) or []:
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    yield url, item
            elif isinstance(item, str) and item.strip():
                yield item, {"type": field}

    for item in person.get("sources") or []:
        if isinstance(item, str) and item.strip():
            yield item, {"type": "source"}
        elif isinstance(item, dict):
            url = item.get("url")
            if isinstance(url, str) and url.strip():
                yield url, item


def person_records_index(payload: Any) -> dict[str, list[dict[str, Any]]]:
    rows = payload.get("people") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        aliases: list[Any] = [row.get("name"), row.get("englishName")]
        aliases.extend(row.get("aliases") or [])
        for alias in aliases:
            key = person_name_key(alias)
            if key:
                result.setdefault(key, []).append(row)
    return result


def core_people_for_track(
    track: dict[str, Any],
    profiles: dict[str, dict[str, Any]],
) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for sample_company in track.get("sampleCompanies") or []:
        profile = None
        for key in company_keys(sample_company):
            profile = profiles.get(key)
            if profile:
                break
        if not profile:
            continue
        company = clean_text(profile.get("name") or sample_company, 120)
        for candidate in choose_core_team(profile, company):
            key = person_name_key(candidate.name)
            if not key or key in seen:
                continue
            seen.add(key)
            result.append((candidate.name, company, candidate.role))
            if len(result) >= MAX_PEOPLE_PER_TRACK:
                return result
    return result


def source_id(person: str, platform: str) -> str:
    return f"source-auto-person-channel-{slugify(person)}-{slugify(platform)}"


def collect_person_channels(records: list[dict[str, Any]]) -> list[PublicChannel]:
    channels: dict[str, PublicChannel] = {}
    for record in records:
        for url, metadata in iter_person_urls(record):
            channel = classify_public_channel(url, metadata)
            if not channel:
                continue
            key = normalize_url(channel.url).casefold()
            existing = channels.get(key)
            if existing is None or channel.priority > existing.priority:
                channels[key] = channel
    return sorted(
        channels.values(),
        key=lambda item: (-item.priority, item.platform, item.url),
    )[:MAX_CHANNELS_PER_PERSON]


def apply_public_channels(
    config: dict[str, Any],
    ledger: dict[str, Any],
    track: dict[str, Any],
    people_records: dict[str, list[dict[str, Any]]],
    profiles: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    slug = str(track.get("slug") or "")
    stamp = now_iso()
    blocked = blocked_values(ledger, track, "sources")
    existing_urls = {
        normalize_url(source.get("url")).casefold()
        for source in config.get("sources", [])
        if normalize_url(source.get("url"))
    }
    existing_ids = {str(source.get("id") or "") for source in config.get("sources", [])}
    added: list[str] = []

    for person, company, role in core_people_for_track(track, profiles):
        records = people_records.get(person_name_key(person), [])
        if not records:
            continue
        for channel in collect_person_channels(records):
            url = normalize_url(channel.url)
            url_key = url.casefold()
            if not url or url_key in existing_urls or normalized_key(url) in blocked:
                continue

            base = source_id(person, channel.platform)
            unique_id = base
            suffix = 2
            while unique_id in existing_ids:
                unique_id = f"{base}-{suffix}"
                suffix += 1

            keywords: list[str] = []
            for value in (person, company, role):
                cleaned = clean_text(value, 120)
                if cleaned and normalized_key(cleaned) not in {
                    normalized_key(item) for item in keywords
                }:
                    keywords.append(cleaned)

            config.setdefault("sources", []).append(
                {
                    "id": unique_id,
                    "name": f"{person} · {channel.platform}",
                    "url": url,
                    "sourceType": "listing-search",
                    "sourceCategory": "person",
                    "region": "中国"
                    if channel.platform in {"微信公开材料", "知乎", "即刻", "小红书"}
                    else "全球",
                    "sector": str(track.get("name") or "未分类"),
                    "company": "",
                    "ticker": "",
                    "keywords": keywords,
                    "enabled": True,
                }
            )
            existing_urls.add(url_key)
            existing_ids.add(unique_id)
            added.append(url)
            add_ledger_entry(
                ledger,
                slug,
                "sources",
                url,
                [
                    "sample-company-core-team",
                    "verified-public-channel",
                    channel.platform,
                ],
                stamp,
            )

    if added:
        ledger.setdefault("tracks", {}).setdefault(slug, {})[
            "lastPublicChannelExpandedAt"
        ] = stamp
    return {"track": slug, "added": added}


def enrich_public_channels(
    config: dict[str, Any],
    venture_payload: Any,
    people_payload: Any,
    ledger: dict[str, Any],
    max_tracks: int,
) -> dict[str, Any]:
    profiles = profile_index(venture_payload)
    people_records = person_records_index(people_payload)
    tracks = [
        track
        for track in config.get("tracks", [])
        if track.get("enabled") and track.get("sampleCompanies")
    ][:max_tracks]
    summaries = [
        apply_public_channels(config, ledger, track, people_records, profiles)
        for track in tracks
    ]
    return {
        "changed": any(summary["added"] for summary in summaries),
        "tracks": summaries,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--ledger", type=Path, default=LEDGER_PATH)
    parser.add_argument("--venture-profiles", type=Path, default=VENTURE_PROFILES_PATH)
    parser.add_argument("--people", type=Path, default=PEOPLE_PATH)
    parser.add_argument("--max-tracks", type=int, default=30)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(args.config, {"schemaVersion": 1, "tracks": [], "sources": []})
    ledger = load_json(args.ledger, empty_ledger())
    venture_payload = load_json(args.venture_profiles, {"companies": {}})
    people_payload = load_json(args.people, {"people": []})

    tombstones_changed = sync_tombstones(ledger, config)
    result = enrich_public_channels(
        config,
        venture_payload,
        people_payload,
        ledger,
        max(1, args.max_tracks),
    )
    changed = bool(result["changed"] or tombstones_changed)
    if changed:
        stamp = now_iso()
        ledger["updatedAt"] = stamp
        args.config.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        args.ledger.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "changed": changed,
                "addedSourceCount": sum(len(item["added"]) for item in result["tracks"]),
                "tracks": result["tracks"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
