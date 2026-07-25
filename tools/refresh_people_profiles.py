#!/usr/bin/env python3
"""Build public person research profiles from all enabled tracking sectors.

The pipeline deliberately separates identity hints from factual enrichment:
1. collect and de-duplicate configured people across sectors;
2. reject organization/media accounts from the people channel;
3. enrich every person through the same Wikipedia/Wikidata routine;
4. merge official profile links and matching public intelligence;
5. preserve the last trustworthy snapshot when remote sources fail.

No generated field is invented: unsourced sections remain empty and the UI labels
those sections as pending.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
OVERRIDES_PATH = ROOT / "config" / "person_profile_overrides.json"
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
OUTPUT_PATH = ROOT / "public" / "data" / "people.json"

USER_AGENT = "No1Lize-PeopleResearch/1.0 (https://github.com/No1Lize/No1Lize.github.io)"
REQUEST_TIMEOUT = 12
MAX_ARTICLE_MATERIALS = 12

ORG_MARKERS = {
    "company", "official", "university", "foundation", "institute", "laboratory",
    "lab", "media", "news", "post", "capital", "ventures", "research", "team",
    "anthropic", "openai", "deepmind", "washingtonpost",
    "公司", "大学", "研究院", "实验室", "媒体", "新闻", "基金", "资本", "官方",
}
SPEECH_MARKERS = {
    "speech", "keynote", "talk", "lecture", "interview", "podcast", "conversation",
    "演讲", "主题演讲", "采访", "访谈", "对话", "播客", "公开课", "问答",
}
BOOK_MARKERS = {"book", "memoir", "autobiography", "almanack", "著作", "书", "传记"}


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def unique(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        value = str(value or "").strip()
        key = normalize(value)
        if not value or not key or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", value.casefold())


def parse_tracking_label(raw: str) -> tuple[str, str]:
    value = str(raw or "").strip()
    match = re.match(r"^(.*?)\s+@([A-Za-z0-9_]{1,30})$", value)
    if not match:
        return value, ""
    return match.group(1).strip(), match.group(2).strip()


def fallback_slug(name: str, handle: str = "") -> str:
    source = handle or name
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", source.casefold()).strip("-")
    if ascii_slug:
        return ascii_slug
    return f"person-{hashlib.sha1(name.encode('utf-8')).hexdigest()[:10]}"


def is_organization_account(raw: str, name: str, handle: str, explicit_orgs: set[str]) -> bool:
    if normalize(raw) in explicit_orgs:
        return True
    tokens = re.findall(r"[A-Za-z\u3400-\u9fff]+", f"{name} {handle}".casefold())
    return any(token in ORG_MARKERS for token in tokens)


def request_json(url: str) -> dict[str, Any] | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError):
        return None


def candidate_score(title: str, aliases: list[str]) -> float:
    normalized_title = normalize(title)
    if not normalized_title:
        return 0
    best = 0.0
    for alias in aliases:
        normalized_alias = normalize(alias)
        if not normalized_alias:
            continue
        if normalized_title == normalized_alias:
            best = max(best, 100.0)
        elif normalized_alias in normalized_title or normalized_title in normalized_alias:
            best = max(best, 70.0)
        else:
            title_tokens = set(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", title.casefold()))
            alias_tokens = set(re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", alias.casefold()))
            if alias_tokens:
                best = max(best, 50.0 * len(title_tokens & alias_tokens) / len(alias_tokens))
    return best


def fetch_wikipedia(aliases: list[str], queries: list[str] | None = None) -> dict[str, str] | None:
    queries = unique(queries or aliases)
    for language in ("zh", "en"):
        for query in queries[:3]:
            params = urllib.parse.urlencode({
                "action": "query",
                "generator": "search",
                "gsrsearch": query,
                "gsrlimit": 4,
                "prop": "extracts|info|pageprops",
                "exintro": 1,
                "explaintext": 1,
                "inprop": "url",
                "format": "json",
                "origin": "*",
            })
            payload = request_json(f"https://{language}.wikipedia.org/w/api.php?{params}")
            pages = ((payload or {}).get("query") or {}).get("pages") or {}
            ranked: list[tuple[float, dict[str, Any]]] = []
            for page in pages.values():
                props = page.get("pageprops") or {}
                extract = str(page.get("extract") or "").strip()
                if "disambiguation" in props or not extract:
                    continue
                score = candidate_score(str(page.get("title") or ""), aliases)
                if score >= 55:
                    ranked.append((score, page))
            if not ranked:
                continue
            _, page = max(ranked, key=lambda item: item[0])
            return {
                "title": str(page.get("title") or ""),
                "extract": str(page.get("extract") or "").strip(),
                "url": str(page.get("fullurl") or ""),
                "language": language,
                "wikidataId": str((page.get("pageprops") or {}).get("wikibase_item") or ""),
            }
    return None


def wikidata_labels(ids: list[str], language: str = "zh") -> dict[str, str]:
    ids = unique(ids)
    if not ids:
        return {}
    params = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": "|".join(ids[:50]),
        "props": "labels",
        "languages": f"{language}|en",
        "format": "json",
        "origin": "*",
    })
    payload = request_json(f"https://www.wikidata.org/w/api.php?{params}") or {}
    result: dict[str, str] = {}
    for entity_id, entity in (payload.get("entities") or {}).items():
        labels = entity.get("labels") or {}
        label = (labels.get(language) or labels.get("en") or {}).get("value")
        if label:
            result[entity_id] = str(label)
    return result


def claim_ids(entity: dict[str, Any], property_id: str) -> list[str]:
    result: list[str] = []
    for claim in ((entity.get("claims") or {}).get(property_id) or []):
        value = (((claim.get("mainsnak") or {}).get("datavalue") or {}).get("value") or {})
        entity_id = value.get("id") if isinstance(value, dict) else None
        if entity_id:
            result.append(str(entity_id))
    return result


def fetch_wikidata_entity(entity_id: str, language: str = "zh") -> dict[str, Any] | None:
    if not entity_id:
        return None
    entity_payload = request_json(f"https://www.wikidata.org/wiki/Special:EntityData/{entity_id}.json") or {}
    entity = (entity_payload.get("entities") or {}).get(entity_id)
    if not entity:
        return None
    descriptions = entity.get("descriptions") or {}
    description = str(((descriptions.get(language) or descriptions.get("en") or {}).get("value")) or "")
    grouped_ids = {
        "roles": claim_ids(entity, "P106"),
        "organizations": claim_ids(entity, "P108") + claim_ids(entity, "P1416"),
        "works": claim_ids(entity, "P800"),
        "education": claim_ids(entity, "P69"),
    }
    labels = wikidata_labels(unique(value for values in grouped_ids.values() for value in values), language)
    return {
        "id": entity_id,
        "url": f"https://www.wikidata.org/wiki/{entity_id}",
        "description": description,
        **{key: unique(labels.get(value, "") for value in values) for key, values in grouped_ids.items()},
    }


def fetch_wikidata(
    aliases: list[str],
    preferred_id: str = "",
    queries: list[str] | None = None,
    identity_terms: list[str] | None = None,
) -> dict[str, Any] | None:
    if preferred_id:
        return fetch_wikidata_entity(preferred_id)
    expected = [normalize(value) for value in unique(identity_terms or []) if len(normalize(value)) >= 3]
    for language in ("zh", "en"):
        for query in unique(queries or aliases)[:4]:
            params = urllib.parse.urlencode({
                "action": "wbsearchentities",
                "search": query,
                "language": language,
                "uselang": language,
                "type": "item",
                "limit": 5,
                "format": "json",
                "origin": "*",
            })
            payload = request_json(f"https://www.wikidata.org/w/api.php?{params}") or {}
            ranked: list[tuple[float, dict[str, Any]]] = []
            for item in payload.get("search") or []:
                score = candidate_score(str(item.get("label") or ""), aliases)
                description = str(item.get("description") or "")
                normalized_description = normalize(description)
                identity_hits = sum(1 for term in expected if term and term in normalized_description)
                lowered_description = description.casefold()
                if any(marker in lowered_description for marker in ("company", "organization", "organisation", "公司", "组织")):
                    score -= 60
                if score >= 55 and identity_hits > 0:
                    ranked.append((score + min(identity_hits, 3) * 8, item))
            if not ranked:
                continue
            _, item = max(ranked, key=lambda pair: pair[0])
            return fetch_wikidata_entity(str(item.get("id") or ""), language)
    return None

def material_type(title: str, event_type: str = "") -> str:
    lowered = title.casefold()
    if event_type == "论文" or any(marker in lowered for marker in ("paper", "arxiv", "论文")):
        return "research_paper"
    if any(marker in lowered for marker in SPEECH_MARKERS):
        return "speech"
    if any(marker in lowered for marker in BOOK_MARKERS):
        return "authored_work"
    if event_type == "人物观点":
        return "public_post"
    return "article"


def matching_articles(candidate: dict[str, Any], articles: list[dict[str, Any]]) -> list[dict[str, str]]:
    aliases = unique(candidate["aliases"] + candidate.get("handles", []))
    normalized_aliases = [normalize(value) for value in aliases if len(normalize(value)) >= 3]
    matches: list[dict[str, str]] = []
    for article in articles:
        haystack = " ".join([
            str(article.get("title") or ""),
            str(article.get("summary") or ""),
            " ".join(str(value) for value in article.get("authors") or []),
        ])
        normalized_haystack = normalize(haystack)
        if not any(alias and alias in normalized_haystack for alias in normalized_aliases):
            continue
        source = article.get("source") or {}
        url = str(source.get("url") or "")
        if not url:
            continue
        matches.append({
            "title": str(article.get("title") or "公开动态"),
            "date": str(article.get("publishedAt") or "持续更新"),
            "type": material_type(str(article.get("title") or ""), str(article.get("type") or "")),
            "url": url,
            "source": str(source.get("name") or source.get("platform") or "公开来源"),
        })
    matches.sort(key=lambda item: item["date"], reverse=True)
    return matches[:MAX_ARTICLE_MATERIALS]


def dedupe_materials(materials: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for material in materials:
        url = str(material.get("url") or "").strip()
        title = str(material.get("title") or "").strip()
        key = url.casefold() or normalize(title)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append({
            "title": title or "公开材料",
            "date": str(material.get("date") or "持续更新"),
            "type": str(material.get("type") or "public_document"),
            "url": url,
            "source": str(material.get("source") or "公开来源"),
        })
    return result


def collect_candidates(tracking: dict[str, Any], overrides: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    explicit_orgs = {normalize(value) for value in overrides.get("organizationAccounts") or []}
    override_index: dict[str, dict[str, Any]] = {}
    for item in overrides.get("people") or []:
        for alias in unique([item.get("canonicalName", ""), item.get("englishName", ""), *(item.get("aliases") or [])]):
            override_index[normalize(alias)] = item

    grouped: dict[str, dict[str, Any]] = {}
    excluded: list[str] = []
    for track in tracking.get("tracks") or []:
        if track.get("enabled") is False:
            continue
        sector = str(track.get("name") or track.get("slug") or "未分类")
        for raw in track.get("people") or []:
            name, handle = parse_tracking_label(str(raw))
            override = override_index.get(normalize(name)) or override_index.get(normalize(str(raw)))
            if is_organization_account(str(raw), name, handle, explicit_orgs):
                excluded.append(str(raw))
                continue
            canonical = str((override or {}).get("canonicalName") or name).strip()
            if not canonical:
                continue
            slug = str((override or {}).get("slug") or fallback_slug(canonical, handle))
            entry = grouped.setdefault(slug, {
                "slug": slug,
                "name": canonical,
                "englishName": str((override or {}).get("englishName") or canonical),
                "aliases": [],
                "handles": [],
                "sectors": [],
                "override": override or {},
            })
            entry["aliases"] = unique([*entry["aliases"], name, canonical, str((override or {}).get("englishName") or ""), *((override or {}).get("aliases") or [])])
            entry["handles"] = unique([*entry["handles"], handle, *((override or {}).get("handles") or [])])
            entry["sectors"] = unique([*entry["sectors"], sector])
    return sorted(grouped.values(), key=lambda item: (item["sectors"][0], item["englishName"])), unique(excluded)


def enrich_candidate(candidate: dict[str, Any], previous: dict[str, Any] | None, articles: list[dict[str, Any]], offline: bool) -> dict[str, Any]:
    override = candidate["override"]
    aliases = unique([candidate["name"], candidate["englishName"], *candidate["aliases"]])
    identity_queries = unique([*(override.get("wikipediaQueries") or []), *aliases])
    identity_terms = unique([
        *(override.get("organizationHints") or []),
        str(override.get("roleHint") or ""),
        *(override.get("productHints") or []),
        *candidate.get("sectors", []),
    ])
    wikipedia = None if offline else fetch_wikipedia(aliases, identity_queries)
    wikidata = None if offline else fetch_wikidata(
        aliases,
        preferred_id=str((wikipedia or {}).get("wikidataId") or ""),
        queries=identity_queries,
        identity_terms=identity_terms,
    )

    previous = previous or {}
    official_materials = [
        {
            "title": item.get("title") or "官方资料",
            "date": "持续更新",
            "type": item.get("type") or "official_profile",
            "url": item.get("url") or "",
            "source": item.get("source") or "官方网站",
        }
        for item in override.get("officialSources") or []
    ]
    reference_materials: list[dict[str, Any]] = []
    if wikipedia and wikipedia.get("url"):
        reference_materials.append({
            "title": f"{wikipedia['title']} — Wikipedia",
            "date": "持续更新",
            "type": "biography",
            "url": wikipedia["url"],
            "source": f"Wikipedia ({wikipedia['language']})",
        })
    if wikidata and wikidata.get("url"):
        reference_materials.append({
            "title": f"{candidate['englishName']} — Wikidata",
            "date": "持续更新",
            "type": "public_document",
            "url": wikidata["url"],
            "source": "Wikidata",
        })

    article_materials = matching_articles(candidate, articles)
    materials = dedupe_materials([
        *official_materials,
        *reference_materials,
        *article_materials,
        *(previous.get("materials") or []),
    ])

    wiki_extract = str((wikipedia or {}).get("extract") or "").strip()
    background = wiki_extract or str(previous.get("background") or "").strip()
    summary = (background.split("\n", 1)[0][:520] if background else "") or str(previous.get("summary") or "").strip()
    if not summary:
        summary = str(override.get("roleHint") or "公开背景资料待补充。")

    roles = unique([str(override.get("roleHint") or ""), *((wikidata or {}).get("roles") or []), str(previous.get("role") or "")])
    organizations = unique([*(override.get("organizationHints") or []), *((wikidata or {}).get("organizations") or []), *(previous.get("organizations") or [])])
    products = unique([*(override.get("productHints") or []), *(previous.get("products") or [])])
    works = unique([*((wikidata or {}).get("works") or []), *(previous.get("works") or [])])
    books = unique([value for value in works if any(marker in value.casefold() for marker in BOOK_MARKERS)] + list(previous.get("books") or []))
    speeches = [item for item in materials if item["type"] in {"speech", "interview", "qa"}]
    concepts = unique([*products, *candidate["sectors"], *(previous.get("concepts") or [])])[:8]

    source_urls = unique([
        *(([wikipedia.get("url")] if wikipedia else [])),
        *(([wikidata.get("url")] if wikidata else [])),
        *(str(item.get("url") or "") for item in override.get("officialSources") or []),
    ])
    status = "complete" if background and len(materials) >= 4 else "partial" if materials else "pending"

    return {
        "slug": candidate["slug"],
        "name": candidate["name"],
        "englishName": candidate["englishName"],
        "aliases": aliases,
        "handles": candidate["handles"],
        "sectors": candidate["sectors"],
        "role": roles[0] if roles else "人物档案待补充",
        "summary": summary,
        "background": background,
        "concepts": concepts,
        "organizations": organizations,
        "products": products,
        "works": works,
        "books": books,
        "speeches": speeches,
        "materials": materials,
        "sources": source_urls,
        "status": status,
        "updatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def build_payload(offline: bool = False, workers: int = 6) -> dict[str, Any]:
    tracking = load_json(TRACKING_PATH, {"tracks": []})
    overrides = load_json(OVERRIDES_PATH, {"people": [], "organizationAccounts": []})
    article_payload = load_json(ARTICLES_PATH, {"articles": []})
    previous_payload = load_json(OUTPUT_PATH, {"people": []})
    previous = {item.get("slug"): item for item in previous_payload.get("people") or [] if item.get("slug")}
    candidates, excluded = collect_candidates(tracking, overrides)

    if workers <= 1:
        people = [enrich_candidate(item, previous.get(item["slug"]), article_payload.get("articles") or [], offline) for item in candidates]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(enrich_candidate, item, previous.get(item["slug"]), article_payload.get("articles") or [], offline)
                for item in candidates
            ]
            people = [future.result() for future in futures]

    people.sort(key=lambda item: (item["sectors"][0] if item["sectors"] else "", item["englishName"]))
    return {
        "schemaVersion": 1,
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "personCount": len(people),
        "excludedOrganizationAccounts": excluded,
        "people": people,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Skip Wikipedia and Wikidata requests.")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    payload = build_payload(offline=args.offline, workers=max(1, args.workers))
    if payload["personCount"] < 1:
        print("No tracked people were generated.", file=sys.stderr)
        return 1
    invalid = [item["slug"] for item in payload["people"] if not item.get("name") or not item.get("materials")]
    if args.validate_only:
        if invalid:
            print(f"Profiles missing required identity/materials: {invalid}", file=sys.stderr)
            return 1
        print(f"Validated {payload['personCount']} tracked people profiles.")
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {payload['personCount']} people profiles to {OUTPUT_PATH.relative_to(ROOT)}")
    if invalid:
        print(f"Warning: incomplete profiles: {invalid}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
