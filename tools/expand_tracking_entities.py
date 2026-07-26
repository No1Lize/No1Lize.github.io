#!/usr/bin/env python3
"""Expand tracking entities from public web sources and sync the config.

For every enabled track the tool takes the existing seeds (track name,
keywords, people, sample companies), queries only public, no-login web
endpoints (Wikipedia, Wikidata, OpenAlex, Baidu/Google suggest), scores
closely-related candidate keywords, people, companies and official-site
sources, and writes accepted candidates straight into
``config/user_tracking.json`` — the same file the /tracking admin edits, so
the existing crawler pipeline picks them up on the next refresh.

Rules that keep the loop safe:

- a candidate is only accepted when it is validated with the same rules the
  /tracking admin UI enforces (mirrored from lib/user-tracking.ts);
- every automatic addition is remembered in
  ``config/tracking_auto_discovery.json``; when the site owner later deletes
  an auto-added entry (or it appears in ``ignoredRecommendations``), it
  becomes a tombstone and is never added again;
- a brand-new custom track with an empty keyword list is seeded first: its
  name alone is expanded on the web and the top keywords are imported
  directly into the keyword area;
- when the network is unreachable the tool changes nothing — it never
  fabricates entities.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, quote_plus
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "user_tracking.json"
LEDGER_PATH = ROOT / "config" / "tracking_auto_discovery.json"

USER_AGENT = (
    "No1LizeResearch/1.0 (+https://github.com/No1Lize/No1Lize.github.io; "
    "public tracking entity discovery)"
)
REQUEST_TIMEOUT = 20
REQUEST_SLEEP = 0.35

MAX_KEYWORDS_PER_RUN = 5
MAX_SEED_KEYWORDS = 8
MAX_PEOPLE_PER_RUN = 2
MAX_COMPANIES_PER_RUN = 3
MAX_SOURCES_PER_RUN = 2
MAX_TRACK_KEYWORDS = 45
MAX_TRACK_PEOPLE = 25
MAX_TRACK_COMPANIES = 30
ACCEPT_THRESHOLD = 3.0
SEED_ACCEPT_THRESHOLD = 2.0

COMPANY_CLASSES = {
    "Q4830453",  # business
    "Q891723",  # public company
    "Q6881511",  # enterprise
    "Q783794",  # company
    "Q161726",  # multinational corporation
    "Q1058914",  # software company
    "Q18388277",  # technology company
    "Q207652",  # chemical company
    "Q43229",  # organization (weak, only with website)
}
HUMAN_CLASS = "Q5"
COUNTRY_REGIONS = {"Q148": "中国", "Q30": "美国"}

GENERIC_TRACKING_KEYWORDS = {
    "ai",
    "ml",
    "人工智能",
    "技术",
    "科技",
    "公司",
    "企业",
    "行业",
    "产业",
    "研究",
    "论文",
    "新闻",
    "资讯",
    "产品",
    "项目",
    "模型",
    "系统",
    "平台",
    "创新",
    "投资",
    "融资",
    "上市",
    "发布",
    "突破",
    "发展",
    "市场",
    "应用",
    "机器人",
    "半导体",
    "新能源",
    "生物科技",
    "量子计算",
    "商业航天",
    "web3",
    "新材料",
    "智能制造",
    "tech",
    "technology",
    "company",
    "industry",
    "research",
    "paper",
    "news",
    "product",
    "project",
    "model",
    "system",
    "platform",
    "innovation",
    "investment",
    "startup",
    "价格",
    "招聘",
    "股票",
    "概念股",
    "龙头股",
    "是什么",
    "什么意思",
    "怎么样",
    "官网",
    "下载",
    "培训",
    "招标",
}
GENERIC_SUFFIXES = ("是什么", "什么意思", "怎么样", "官网", "招聘", "股吧", "股票")

FetchJson = Callable[[str], Any]
FetchText = Callable[[str], str]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def normalize_term(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(value or ""))
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.casefold()


def clean_candidate(value: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(value or ""))
    cleaned = re.sub(r"[\"'“”‘’`]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -·:：,，。.;；")
    return cleaned.strip()


def validate_keyword(value: str) -> str:
    """Mirror lib/user-tracking.ts validateTrackingKeyword; return normalized
    keyword or empty string when rejected."""

    raw = clean_candidate(value)[:80]
    if not raw or len(raw) > 40:
        return ""
    if re.search(r"^https?://", raw, re.IGNORECASE):
        return ""
    if re.search(r"\b(?:www\.)?[^\s]+\.(?:com|cn|org|net)\b", raw, re.IGNORECASE):
        return ""
    if "@" in raw:
        return ""
    if re.search(r"^site\s*:", raw, re.IGNORECASE):
        return ""
    if re.search(r"(^|\s)(?:AND|OR|NOT)(\s|$)", raw):
        return ""
    if not re.search(r"[A-Za-z0-9㐀-鿿]", raw):
        return ""
    if normalize_term(raw) in GENERIC_TRACKING_KEYWORDS:
        return ""
    if any(raw.endswith(suffix) for suffix in GENERIC_SUFFIXES):
        return ""
    cjk = len(re.findall(r"[㐀-鿿]", raw))
    alnum = len(re.findall(r"[A-Za-z0-9]", raw))
    if cjk == 1 and alnum == 0:
        return ""
    if cjk == 0 and alnum < 2:
        return ""
    return raw


def validate_person(display_name: str, handle: str = "") -> str:
    name = clean_candidate(display_name)[:100]
    if not name or not re.search(r"[A-Za-z0-9㐀-鿿]", name):
        return ""
    if re.search(r"https?://|@", name):
        return ""
    if handle and re.fullmatch(r"[A-Za-z0-9_]{1,15}", handle):
        return f"{name} @{handle}"
    return name


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore")
    text = re.sub(r"[^a-z0-9]+", "-", normalized.decode("ascii").lower()).strip("-")
    if text:
        return text
    digest = hashlib.md5(value.encode("utf-8")).hexdigest()[:8]
    return f"item-{digest}"


@dataclass
class Candidate:
    value: str
    score: float = 0.0
    evidence: set[str] = field(default_factory=set)
    entity_id: str = ""
    website: str = ""
    region: str = "全球"
    handle: str = ""


class PublicWebClient:
    """Thin wrapper over public keyless endpoints with a request budget."""

    def __init__(
        self,
        max_requests: int,
        fetch_text: FetchText | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.max_requests = max_requests
        self.used_requests = 0
        self.failed_requests = 0
        self._fetch_text = fetch_text or self._default_fetch_text
        self._sleep = sleep

    def _default_fetch_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset, errors="replace")

    def text(self, url: str) -> str:
        if self.used_requests >= self.max_requests:
            raise BudgetExhausted()
        self.used_requests += 1
        try:
            body = self._fetch_text(url)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            self.failed_requests += 1
            return ""
        self._sleep(REQUEST_SLEEP)
        return body

    def json(self, url: str) -> Any:
        body = self.text(url)
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return None


class BudgetExhausted(Exception):
    pass


def wikipedia_resolve(client: PublicWebClient, term: str, lang: str) -> str:
    data = client.json(
        f"https://{lang}.wikipedia.org/w/api.php?action=opensearch"
        f"&search={quote_plus(term)}&limit=1&namespace=0&format=json"
    )
    if isinstance(data, list) and len(data) >= 2 and data[1]:
        return str(data[1][0])
    return ""


def wikipedia_morelike(client: PublicWebClient, title: str, lang: str) -> list[str]:
    data = client.json(
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search"
        f"&srsearch=morelike:{quote(title)}&srlimit=10&format=json"
    )
    results = (
        data.get("query", {}).get("search", []) if isinstance(data, dict) else []
    )
    return [str(row.get("title", "")) for row in results if row.get("title")]


def baidu_suggest(client: PublicWebClient, term: str) -> list[str]:
    body = client.text(
        f"https://suggestion.baidu.com/su?wd={quote_plus(term)}&cb=window.baidu.sug"
    )
    match = re.search(r"s\s*:\s*\[(.*?)\]", body)
    if not match:
        return []
    return [
        value.strip().strip('"')
        for value in match.group(1).split('","')
        if value.strip().strip('"')
    ]


def google_suggest(client: PublicWebClient, term: str) -> list[str]:
    data = client.json(
        "https://suggestqueries.google.com/complete/search?client=firefox"
        f"&q={quote_plus(term)}"
    )
    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
        return [str(value) for value in data[1]]
    return []


def openalex_related_concepts(client: PublicWebClient, term: str) -> list[str]:
    data = client.json(
        f"https://api.openalex.org/concepts?search={quote_plus(term)}&per-page=1"
    )
    results = data.get("results") if isinstance(data, dict) else None
    if not results:
        return []
    related = results[0].get("related_concepts") or []
    names: list[str] = []
    for row in related:
        if float(row.get("score") or 0) < 0.4:
            continue
        name = str(row.get("display_name") or "")
        if name:
            names.append(name)
    return names[:8]


def wikidata_lookup(client: PublicWebClient, term: str) -> dict[str, Any]:
    """Classify a candidate: kind (company/person/keyword) + enrichment."""

    for language in ("zh", "en"):
        search = client.json(
            "https://www.wikidata.org/w/api.php?action=wbsearchentities"
            f"&search={quote_plus(term)}&language={language}&format=json&limit=1"
        )
        rows = search.get("search") if isinstance(search, dict) else None
        if not rows:
            continue
        entity_id = str(rows[0].get("id") or "")
        if not entity_id:
            continue
        detail = client.json(
            "https://www.wikidata.org/w/api.php?action=wbgetentities"
            f"&ids={entity_id}&props=claims&format=json"
        )
        claims = (
            detail.get("entities", {}).get(entity_id, {}).get("claims", {})
            if isinstance(detail, dict)
            else {}
        )

        def claim_ids(prop: str) -> list[str]:
            values = []
            for row in claims.get(prop, []):
                value = (
                    row.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value", {})
                )
                if isinstance(value, dict) and value.get("id"):
                    values.append(str(value["id"]))
            return values

        def claim_strings(prop: str) -> list[str]:
            values = []
            for row in claims.get(prop, []):
                value = (
                    row.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value")
                )
                if isinstance(value, str):
                    values.append(value)
            return values

        instance_of = set(claim_ids("P31"))
        kind = "keyword"
        if HUMAN_CLASS in instance_of:
            kind = "person"
        elif instance_of & COMPANY_CLASSES:
            kind = "company"
        websites = claim_strings("P856")
        countries = claim_ids("P17")
        handles = claim_strings("P2002")
        region = "全球"
        for country in countries:
            if country in COUNTRY_REGIONS:
                region = COUNTRY_REGIONS[country]
                break
        return {
            "id": entity_id,
            "kind": kind,
            "website": websites[0] if websites else "",
            "region": region,
            "handle": handles[0] if handles else "",
        }
    return {}


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def empty_ledger() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "updatedAt": "",
        "tracks": {},
        "added": [],
        "removed": [],
    }


def ledger_key(track: str, kind: str, value: str) -> tuple[str, str, str]:
    return (track, kind, normalize_term(value))


def config_values(track: dict[str, Any], kind: str, config: dict[str, Any]) -> list[str]:
    if kind == "sources":
        return [
            str(source.get("url") or "")
            for source in config.get("sources", [])
            if source.get("sector") == track.get("name")
        ]
    return [str(value) for value in track.get(kind, [])]


def sync_tombstones(ledger: dict[str, Any], config: dict[str, Any]) -> None:
    """Auto-added entries that the owner has deleted become tombstones."""

    tracks_by_slug = {track.get("slug"): track for track in config.get("tracks", [])}
    still_added: list[dict[str, Any]] = []
    removed = ledger.setdefault("removed", [])
    removed_keys = {
        ledger_key(row.get("track", ""), row.get("kind", ""), row.get("value", ""))
        for row in removed
    }
    for row in ledger.get("added", []):
        track = tracks_by_slug.get(row.get("track"))
        present = False
        if track:
            values = {
                normalize_term(value)
                for value in config_values(track, str(row.get("kind")), config)
            }
            present = normalize_term(str(row.get("value"))) in values
        if present:
            still_added.append(row)
            continue
        key = ledger_key(
            str(row.get("track")), str(row.get("kind")), str(row.get("value"))
        )
        if key not in removed_keys:
            removed.append(
                {
                    "track": row.get("track"),
                    "kind": row.get("kind"),
                    "value": row.get("value"),
                    "removedAt": now_iso(),
                }
            )
            removed_keys.add(key)
    ledger["added"] = still_added


def blocked_values(
    ledger: dict[str, Any], track: dict[str, Any], kind: str
) -> set[str]:
    slug = str(track.get("slug"))
    blocked = {
        normalize_term(str(row.get("value")))
        for row in ledger.get("removed", [])
        if row.get("track") == slug and row.get("kind") == kind
    }
    ignored = track.get("ignoredRecommendations") or {}
    ignored_kind = {
        "keywords": "keywords",
        "people": "people",
        "sampleCompanies": "companies",
        "sources": "sources",
    }[kind]
    for value in ignored.get(ignored_kind, []) or []:
        blocked.add(normalize_term(str(value)))
    return blocked


def track_seed_terms(track: dict[str, Any], seeding: bool) -> list[str]:
    seeds: list[str] = [str(track.get("name") or "")]
    if not seeding:
        seeds.extend(str(value) for value in (track.get("keywords") or [])[:6])
        seeds.extend(str(value) for value in (track.get("sampleCompanies") or [])[:4])
        for person in (track.get("people") or [])[:3]:
            seeds.append(re.sub(r"@\S+", "", str(person)).strip())
    unique: list[str] = []
    seen: set[str] = set()
    for seed in seeds:
        cleaned = clean_candidate(seed)
        key = normalize_term(cleaned)
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique[:8]


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[㐀-鿿]", value))


def gather_candidates(
    client: PublicWebClient, seeds: list[str]
) -> dict[str, Candidate]:
    pool: dict[str, Candidate] = {}

    def bump(value: str, weight: float, evidence: str) -> None:
        cleaned = clean_candidate(value)
        if not cleaned or len(cleaned) > 60:
            return
        key = normalize_term(cleaned)
        if not key or any(normalize_term(seed) == key for seed in seeds):
            return
        candidate = pool.setdefault(key, Candidate(value=cleaned))
        candidate.score += weight
        candidate.evidence.add(evidence)

    for seed in seeds:
        lang = "zh" if has_cjk(seed) else "en"
        try:
            title = wikipedia_resolve(client, seed, lang)
            if title:
                for related in wikipedia_morelike(client, title, lang):
                    bump(related, 2.0, "wikipedia-morelike")
            if has_cjk(seed):
                for suggestion in baidu_suggest(client, seed):
                    trimmed = suggestion.replace(seed, " ").strip()
                    bump(suggestion, 1.0, "baidu-suggest")
                    if trimmed and trimmed != suggestion:
                        bump(f"{seed} {trimmed}".strip(), 0.0, "baidu-suggest")
            else:
                for suggestion in google_suggest(client, seed):
                    bump(suggestion, 1.0, "google-suggest")
                for concept in openalex_related_concepts(client, seed):
                    bump(concept, 2.0, "openalex-related")
        except BudgetExhausted:
            break
    return pool


def expand_track(
    client: PublicWebClient,
    config: dict[str, Any],
    ledger: dict[str, Any],
    track: dict[str, Any],
    all_track_names: set[str],
    dry_run: bool,
) -> dict[str, Any]:
    seeding = not (track.get("keywords") or [])
    seeds = track_seed_terms(track, seeding)
    summary = {
        "track": track.get("slug"),
        "mode": "seed" if seeding else "expand",
        "added": {"keywords": [], "people": [], "sampleCompanies": [], "sources": []},
    }
    if not seeds:
        return summary

    pool = gather_candidates(client, seeds)
    threshold = SEED_ACCEPT_THRESHOLD if seeding else ACCEPT_THRESHOLD
    ranked = sorted(
        (c for c in pool.values() if c.score >= threshold),
        key=lambda c: c.score,
        reverse=True,
    )

    existing = {
        kind: {
            normalize_term(value)
            for value in config_values(track, kind, config)
        }
        for kind in ("keywords", "people", "sampleCompanies", "sources")
    }
    existing_all = (
        existing["keywords"] | existing["people"] | existing["sampleCompanies"]
    )
    blocked = {
        kind: blocked_values(ledger, track, kind)
        for kind in ("keywords", "people", "sampleCompanies", "sources")
    }

    caps = {
        "keywords": MAX_SEED_KEYWORDS if seeding else MAX_KEYWORDS_PER_RUN,
        "people": 0 if seeding else MAX_PEOPLE_PER_RUN,
        "sampleCompanies": 0 if seeding else MAX_COMPANIES_PER_RUN,
        "sources": 0 if seeding else MAX_SOURCES_PER_RUN,
    }
    if len(track.get("keywords") or []) >= MAX_TRACK_KEYWORDS:
        caps["keywords"] = 0
    if len(track.get("people") or []) >= MAX_TRACK_PEOPLE:
        caps["people"] = 0
    if len(track.get("sampleCompanies") or []) >= MAX_TRACK_COMPANIES:
        caps["sampleCompanies"] = 0

    added = summary["added"]
    for candidate in ranked:
        if (
            len(added["keywords"]) >= caps["keywords"]
            and len(added["people"]) >= caps["people"]
            and len(added["sampleCompanies"]) >= caps["sampleCompanies"]
        ):
            break
        value_key = normalize_term(candidate.value)
        if value_key in existing_all or value_key in existing["sources"]:
            continue
        if normalize_term(candidate.value) in {
            normalize_term(name) for name in all_track_names
        }:
            continue

        info: dict[str, Any] = {}
        # Only spend classification requests on strong multi-source candidates.
        if not seeding and len(candidate.evidence) >= 1 and candidate.score >= threshold:
            try:
                info = wikidata_lookup(client, candidate.value)
            except BudgetExhausted:
                info = {}
        kind = str(info.get("kind") or "keyword")

        if kind == "person" and caps["people"] > len(added["people"]):
            label = validate_person(candidate.value, str(info.get("handle") or ""))
            if not label or normalize_term(label) in blocked["people"]:
                continue
            if normalize_term(label) in existing["people"]:
                continue
            added["people"].append(label)
            existing["people"].add(normalize_term(label))
            existing_all.add(value_key)
            continue

        if kind == "company" and caps["sampleCompanies"] > len(added["sampleCompanies"]):
            company = clean_candidate(candidate.value)[:60]
            if not company or normalize_term(company) in blocked["sampleCompanies"]:
                continue
            added["sampleCompanies"].append(company)
            existing["sampleCompanies"].add(normalize_term(company))
            existing_all.add(value_key)
            website = str(info.get("website") or "")
            if (
                website.startswith("http")
                and caps["sources"] > len(added["sources"])
                and normalize_term(website) not in blocked["sources"]
                and normalize_term(website) not in existing["sources"]
            ):
                added["sources"].append(
                    {
                        "id": f"source-auto-{slugify(company)}",
                        "name": f"{company} 官方网站",
                        "url": website,
                        "sourceType": "listing-search",
                        "sourceCategory": "company",
                        "region": str(info.get("region") or "全球"),
                        "sector": str(track.get("name") or "未分类"),
                        "company": company,
                        "ticker": "",
                        "keywords": [company],
                        "enabled": True,
                    }
                )
                existing["sources"].add(normalize_term(website))
            continue

        if caps["keywords"] > len(added["keywords"]):
            keyword = validate_keyword(candidate.value)
            if not keyword or normalize_term(keyword) in blocked["keywords"]:
                continue
            if normalize_term(keyword) in existing["keywords"]:
                continue
            added["keywords"].append(keyword)
            existing["keywords"].add(normalize_term(keyword))
            existing_all.add(value_key)

    if dry_run:
        return summary

    stamp = now_iso()
    for kind in ("keywords", "people", "sampleCompanies"):
        for value in added[kind]:
            track.setdefault(kind, []).append(value)
            ledger["added"].append(
                {
                    "track": track.get("slug"),
                    "kind": kind,
                    "value": value,
                    "addedAt": stamp,
                    "evidence": sorted(
                        pool.get(normalize_term(value), Candidate(value)).evidence
                    ),
                }
            )
    existing_source_ids = {
        str(source.get("id")) for source in config.get("sources", [])
    }
    existing_source_urls = {
        normalize_term(str(source.get("url") or ""))
        for source in config.get("sources", [])
    }
    for source in added["sources"]:
        if source["id"] in existing_source_ids:
            source["id"] = f"{source['id']}-{len(existing_source_ids)}"
        if normalize_term(source["url"]) in existing_source_urls:
            continue
        config.setdefault("sources", []).append(source)
        existing_source_ids.add(source["id"])
        existing_source_urls.add(normalize_term(source["url"]))
        ledger["added"].append(
            {
                "track": track.get("slug"),
                "kind": "sources",
                "value": source["url"],
                "addedAt": stamp,
                "evidence": ["wikidata-official-site"],
            }
        )
    ledger.setdefault("tracks", {})[str(track.get("slug"))] = {
        "lastExpandedAt": stamp
    }
    return summary


def pick_tracks(
    config: dict[str, Any],
    ledger: dict[str, Any],
    only_track: str,
    seed_only: bool,
    max_tracks: int,
) -> list[dict[str, Any]]:
    enabled = [track for track in config.get("tracks", []) if track.get("enabled")]
    if only_track:
        return [track for track in enabled if track.get("slug") == only_track]
    seeding = [track for track in enabled if not (track.get("keywords") or [])]
    if seed_only:
        return seeding
    expandable = [track for track in enabled if track.get("keywords")]

    def last_expanded(track: dict[str, Any]) -> str:
        row = (ledger.get("tracks") or {}).get(str(track.get("slug"))) or {}
        return str(row.get("lastExpandedAt") or "")

    expandable.sort(key=last_expanded)
    remaining = max(0, max_tracks - len(seeding))
    return seeding + expandable[:remaining]


def run(argv: list[str] | None = None, fetch_text: FetchText | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--seed-new-only",
        action="store_true",
        help="only seed brand-new tracks that still have no keywords",
    )
    parser.add_argument("--only-track", default="")
    parser.add_argument("--max-tracks", type=int, default=4)
    parser.add_argument("--max-requests", type=int, default=150)
    args = parser.parse_args(argv)

    config = load_json(CONFIG_PATH, None)
    if not isinstance(config, dict) or not config.get("tracks"):
        print(json.dumps({"error": "config/user_tracking.json unreadable"}))
        return 1
    ledger = load_json(LEDGER_PATH, empty_ledger())
    if not isinstance(ledger, dict):
        ledger = empty_ledger()
    for key, fallback in empty_ledger().items():
        ledger.setdefault(key, fallback)

    sync_tombstones(ledger, config)

    tracks = pick_tracks(
        config, ledger, args.only_track, args.seed_new_only, args.max_tracks
    )
    all_track_names = {
        str(track.get("name") or "") for track in config.get("tracks", [])
    }

    client = PublicWebClient(args.max_requests, fetch_text=fetch_text)
    summaries = []
    for track in tracks:
        summaries.append(
            expand_track(client, config, ledger, track, all_track_names, args.dry_run)
        )

    changed = any(
        any(summary["added"][kind] for kind in summary["added"])
        for summary in summaries
    )
    tombstoned = bool(ledger.get("removed"))
    if not args.dry_run and (changed or tombstoned):
        ledger["updatedAt"] = now_iso()
        LEDGER_PATH.write_text(
            json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if not args.dry_run and changed:
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(
        json.dumps(
            {
                "changed": changed,
                "requestsUsed": client.used_requests,
                "requestsFailed": client.failed_requests,
                "tracks": summaries,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(run())
