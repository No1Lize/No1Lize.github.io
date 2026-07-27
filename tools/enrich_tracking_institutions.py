#!/usr/bin/env python3
"""Sync the venture-capital track from the verified investment-institution profiles.

The investment-institution channel and its detail pages are backed by the
``institutions`` section of ``public/data/venture_profiles.json``. This tool
reuses that same evidence set for the ``风险投资`` tracking lane:

* canonical institution names are added to ``sampleCompanies``;
* founders, managing partners and investment partners are added to ``people``;
* exact public team-page URLs and verified public social accounts are added as
  person sources.

No account is inferred from a name. Entries removed by the owner remain blocked
through the shared auto-discovery tombstone ledger.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from tools.enrich_tracking_people_from_sample_companies import (
    CONFIG_PATH,
    LEDGER_PATH,
    PEOPLE_PATH,
    VENTURE_PROFILES_PATH,
    PublicWikidataClient,
    SocialAccount,
    TeamCandidate,
    add_ledger_entry,
    apply_candidates,
    clean_text,
    company_keys,
    empty_ledger,
    is_likely_person_name,
    ledger_key,
    load_json,
    local_people_index,
    normalized_key,
    now_iso,
    person_name_key,
    slugify,
    sync_tombstones,
    wikidata_social_accounts,
)

MAX_PEOPLE_PER_TRACK = 6
MAX_PEOPLE_PER_INSTITUTION = 3
MAX_INSTITUTIONS_PER_TRACK = 40

INSTITUTION_ROLE_RULES: tuple[tuple[re.Pattern[str], int], ...] = (
    (re.compile(r"创始合伙|联合创始|共同创始|founding\s+partner|co[-\s]?founder", re.I), 130),
    (re.compile(r"管理合伙|主管合伙|managing\s+partner", re.I), 122),
    (re.compile(r"普通合伙|general\s+partner|venture\s+partner", re.I), 116),
    (re.compile(r"投资合伙|合伙人|\bpartner\b", re.I), 108),
    (re.compile(r"董事总经理|managing\s+director|投资负责人|投资总监|head\s+of\s+invest", re.I), 92),
    (re.compile(r"创始人|founder|董事长|chair(?:man|woman|person)?|首席执行|\bceo\b", re.I), 84),
)


def is_investment_track(track: dict[str, Any]) -> bool:
    name = normalized_key(track.get("name"))
    if name in {normalized_key("风险投资"), normalized_key("venture capital")}:
        return True
    keywords = {normalized_key(value) for value in track.get("keywords") or []}
    return normalized_key("私人股权投资") in keywords and normalized_key("天使轮") in keywords


def institution_rows(payload: Any) -> list[dict[str, Any]]:
    institutions = payload.get("institutions") if isinstance(payload, dict) else None
    rows = institutions.values() if isinstance(institutions, dict) else institutions if isinstance(institutions, list) else []
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        name = clean_text(row.get("name"), 120)
        slug = clean_text(row.get("slug"), 120)
        identity = normalized_key(slug or name)
        if not name or not identity or identity in seen:
            continue
        seen.add(identity)
        result.append(row)
    result.sort(key=lambda row: clean_text(row.get("name"), 120).casefold())
    return result


def profile_alias_keys(profile: dict[str, Any]) -> set[str]:
    aliases: list[Any] = [profile.get("name"), profile.get("englishName"), profile.get("slug")]
    aliases.extend(profile.get("aliases") or [])
    keys: set[str] = set()
    for alias in aliases:
        keys.update(company_keys(alias))
    return keys


def institution_index(profiles: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        for key in profile_alias_keys(profile):
            index.setdefault(key, profile)
    return index


def removed_values(ledger: dict[str, Any], track_slug: str, kind: str) -> set[str]:
    return {
        normalized_key(row.get("value"))
        for row in ledger.get("removed", [])
        if row.get("track") == track_slug and row.get("kind") == kind
    }


def sync_sample_institutions(
    track: dict[str, Any],
    profiles: list[dict[str, Any]],
    ledger: dict[str, Any],
) -> list[str]:
    slug = str(track.get("slug") or "")
    samples = track.setdefault("sampleCompanies", [])
    existing_keys: set[str] = set()
    for value in samples:
        existing_keys.update(company_keys(value))
    blocked = removed_values(ledger, slug, "sampleCompanies")
    ignored = track.get("ignoredRecommendations") or {}
    blocked.update(normalized_key(value) for value in ignored.get("companies", []) or [])

    added: list[str] = []
    stamp = now_iso()
    for profile in profiles[:MAX_INSTITUTIONS_PER_TRACK]:
        name = clean_text(profile.get("name"), 120)
        aliases = profile_alias_keys(profile)
        if not name or aliases & existing_keys:
            continue
        if normalized_key(name) in blocked or any(key in blocked for key in aliases):
            continue
        samples.append(name)
        existing_keys.update(aliases)
        added.append(name)
        add_ledger_entry(
            ledger,
            slug,
            "sampleCompanies",
            name,
            ["investment-institution-directory", "verified-institution-profile"],
            stamp,
        )
    return added


def institution_role_score(role: str) -> int:
    cleaned = clean_text(role, 120)
    for pattern, score in INSTITUTION_ROLE_RULES:
        if pattern.search(cleaned):
            return score
    return 0


def choose_institution_team(profile: dict[str, Any], institution: str) -> list[TeamCandidate]:
    candidates: list[TeamCandidate] = []
    for order, row in enumerate(profile.get("team") or []):
        if not isinstance(row, dict):
            continue
        name = clean_text(row.get("name"), 120)
        role = clean_text(row.get("role"), 120)
        score = institution_role_score(role)
        if not score or not is_likely_person_name(name):
            continue
        candidates.append(
            TeamCandidate(
                name=name,
                role=role,
                company=institution,
                source_url=clean_text(row.get("sourceUrl"), 500),
                score=score - order,
            )
        )
    candidates.sort(key=lambda item: (-item.score, item.name))
    unique: list[TeamCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = person_name_key(candidate.name)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
        if len(unique) >= MAX_PEOPLE_PER_INSTITUTION:
            break
    return unique


def discover_institution_people(
    track: dict[str, Any],
    profiles: list[dict[str, Any]],
    local_people: dict[str, list[SocialAccount]],
    client: PublicWikidataClient,
) -> list[TeamCandidate]:
    index = institution_index(profiles)
    candidates: list[TeamCandidate] = []
    seen_people: set[str] = set()
    seen_profiles: set[str] = set()
    for sample in track.get("sampleCompanies") or []:
        profile = None
        for key in company_keys(sample):
            profile = index.get(key)
            if profile:
                break
        if not profile:
            continue
        profile_id = normalized_key(profile.get("slug") or profile.get("name"))
        if not profile_id or profile_id in seen_profiles:
            continue
        seen_profiles.add(profile_id)
        institution = clean_text(profile.get("name") or sample, 120)
        for candidate in choose_institution_team(profile, institution):
            person_key = person_name_key(candidate.name)
            if not person_key or person_key in seen_people:
                continue
            accounts: dict[str, SocialAccount] = {
                account.url.casefold(): account for account in local_people.get(person_key, [])
            }
            for account in wikidata_social_accounts(client, candidate.name, institution):
                accounts[account.url.casefold()] = account
            candidate.socials = list(accounts.values())
            candidates.append(candidate)
            seen_people.add(person_key)
            if len(candidates) >= MAX_PEOPLE_PER_TRACK:
                return candidates
    return candidates


def register_team_pages(
    config: dict[str, Any],
    ledger: dict[str, Any],
    track: dict[str, Any],
    candidates: list[TeamCandidate],
) -> list[str]:
    slug = str(track.get("slug") or "")
    blocked = removed_values(ledger, slug, "sources")
    existing_urls = {normalized_key(source.get("url")) for source in config.get("sources", [])}
    existing_ids = {str(source.get("id") or "") for source in config.get("sources", [])}
    grouped: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        url = clean_text(candidate.source_url, 500)
        if not re.match(r"^https?://", url, re.I):
            continue
        key = normalized_key(url)
        if not key:
            continue
        group = grouped.setdefault(
            key,
            {"url": url, "institution": candidate.company, "people": [], "roles": []},
        )
        group["people"].append(candidate.name)
        if candidate.role:
            group["roles"].append(candidate.role)

    added: list[str] = []
    stamp = now_iso()
    for key, group in grouped.items():
        if key in existing_urls or key in blocked:
            continue
        institution = clean_text(group["institution"], 120)
        base_id = f"source-auto-institution-team-{slugify(institution)}"
        source_id = base_id
        suffix = 2
        while source_id in existing_ids:
            source_id = f"{base_id}-{suffix}"
            suffix += 1
        keywords = list(dict.fromkeys([*group["people"], institution, *group["roles"]]))[:12]
        config.setdefault("sources", []).append(
            {
                "id": source_id,
                "name": f"{institution} · 核心团队页",
                "url": group["url"],
                "sourceType": "listing-search",
                "sourceCategory": "person",
                "region": "全球",
                "sector": str(track.get("name") or "风险投资"),
                "company": institution,
                "ticker": "",
                "keywords": keywords,
                "enabled": True,
            }
        )
        existing_urls.add(key)
        existing_ids.add(source_id)
        added.append(group["url"])
        add_ledger_entry(
            ledger,
            slug,
            "sources",
            group["url"],
            ["investment-institution-directory", "verified-institution-team-page"],
            stamp,
        )
    return added


def enrich_config(
    config: dict[str, Any],
    venture_payload: Any,
    people_payload: Any,
    ledger: dict[str, Any],
    client: PublicWikidataClient,
) -> dict[str, Any]:
    profiles = institution_rows(venture_payload)
    local_people = local_people_index(people_payload)
    summaries: list[dict[str, Any]] = []
    for track in config.get("tracks", []):
        if not track.get("enabled") or not is_investment_track(track):
            continue
        added_samples = sync_sample_institutions(track, profiles, ledger)
        candidates = discover_institution_people(track, profiles, local_people, client)
        summary = apply_candidates(config, ledger, track, candidates)
        team_pages = register_team_pages(config, ledger, track, candidates)
        summary["added"]["sampleCompanies"] = added_samples
        summary["added"]["teamPages"] = team_pages
        if added_samples or summary["added"]["people"] or summary["added"]["sources"] or team_pages:
            ledger.setdefault("tracks", {}).setdefault(str(track.get("slug") or ""), {})[
                "lastInstitutionReferencedAt"
            ] = now_iso()
        summaries.append(summary)
    changed = any(any(values for values in summary["added"].values()) for summary in summaries)
    return {
        "changed": changed,
        "requestsUsed": client.used_requests,
        "requestsFailed": client.failed_requests,
        "institutionProfiles": len(profiles),
        "tracks": summaries,
    }


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--max-requests", type=int, default=80)
    args = parser.parse_args(argv)

    config = load_json(CONFIG_PATH, None)
    if not isinstance(config, dict) or not isinstance(config.get("tracks"), list):
        print(json.dumps({"error": "config/user_tracking.json unreadable"}, ensure_ascii=False))
        return 1
    venture_payload = load_json(VENTURE_PROFILES_PATH, {})
    people_payload = load_json(PEOPLE_PATH, {})
    ledger = load_json(LEDGER_PATH, empty_ledger())
    if not isinstance(ledger, dict):
        ledger = empty_ledger()
    for key, fallback in empty_ledger().items():
        ledger.setdefault(key, fallback)

    tombstoned = sync_tombstones(ledger, config)
    client = PublicWikidataClient(max_requests=max(0, args.max_requests))
    result = enrich_config(config, venture_payload, people_payload, ledger, client)

    if not args.dry_run and (result["changed"] or tombstoned):
        ledger["updatedAt"] = now_iso()
        LEDGER_PATH.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.dry_run and result["changed"]:
        CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["tombstoned"] = tombstoned
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(run())
