#!/usr/bin/env python3
"""Resolve article company entities against the official company registry.

The resolver separates publishable company attribution from low-confidence text
mentions. Explicit slugs, official domains and exact structured company fields
become ``companySlugs``. Free-text title/summary mentions are retained only as
``companyCandidateSlugs`` for later review and never place an article in the
company channel by themselves.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "config" / "official_company_sources.json"
ARTICLES_PATH = ROOT / "public" / "data" / "articles.json"
GENERIC_COMPANIES = {"", "科技产业", "产业", "行业", "公司", "科技公司", "未识别"}


@dataclass(frozen=True)
class CompanyEntity:
    slug: str
    name: str
    aliases: tuple[str, ...]
    domains: tuple[str, ...]
    order: int


@dataclass(frozen=True)
class CompanyRegistry:
    entities: tuple[CompanyEntity, ...]
    by_slug: dict[str, CompanyEntity]
    by_alias: dict[str, tuple[CompanyEntity, ...]]
    by_domain: dict[str, tuple[CompanyEntity, ...]]


def clean(value: Any, limit: int = 1000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def normalize_identity(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+",
        "",
        clean(value, 500).casefold(),
    )


def normalized_host(value: Any) -> str:
    host = (urlsplit(clean(value, 2000)).hostname or "").casefold().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean(value, 300)
        key = normalize_identity(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
    return tuple(result)


def load_registry_payload(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("company registry must be a JSON object")
    return payload


def build_registry(payload: dict[str, Any]) -> CompanyRegistry:
    entities: list[CompanyEntity] = []
    alias_index: dict[str, list[CompanyEntity]] = {}
    domain_index: dict[str, list[CompanyEntity]] = {}

    for order, raw in enumerate(payload.get("companies", [])):
        if not isinstance(raw, dict):
            continue
        slug = clean(raw.get("slug"), 100)
        name = clean(raw.get("name"), 160)
        if not slug or not name:
            continue
        aliases = _unique([name, *(raw.get("aliases") or [])])
        urls: list[str] = [clean(raw.get("homepage"), 2000)]
        urls.extend(clean(url, 2000) for url in (raw.get("newsUrls") or []))
        domains = tuple(
            dict.fromkeys(host for host in (normalized_host(url) for url in urls) if host)
        )
        entity = CompanyEntity(
            slug=slug,
            name=name,
            aliases=aliases,
            domains=domains,
            order=order,
        )
        entities.append(entity)
        for alias in aliases:
            alias_index.setdefault(normalize_identity(alias), []).append(entity)
        for domain in domains:
            domain_index.setdefault(domain, []).append(entity)

    return CompanyRegistry(
        entities=tuple(entities),
        by_slug={entity.slug: entity for entity in entities},
        by_alias={key: tuple(values) for key, values in alias_index.items()},
        by_domain={key: tuple(values) for key, values in domain_index.items()},
    )


def load_registry(path: Path = REGISTRY_PATH) -> CompanyRegistry:
    return build_registry(load_registry_payload(path))


def _domain_matches(host: str, domain: str) -> bool:
    return host == domain or host.endswith(f".{domain}")


def _entities_for_host(host: str, registry: CompanyRegistry) -> list[CompanyEntity]:
    if not host:
        return []
    result: dict[str, CompanyEntity] = {}
    for domain, entities in registry.by_domain.items():
        if not _domain_matches(host, domain):
            continue
        for entity in entities:
            result[entity.slug] = entity
    return sorted(result.values(), key=lambda entity: entity.order)


def _unique_alias_entity(value: Any, registry: CompanyRegistry) -> CompanyEntity | None:
    key = normalize_identity(value)
    entities = registry.by_alias.get(key, ())
    return entities[0] if len(entities) == 1 else None


def _safe_text_alias(alias: str) -> bool:
    cjk_length = len(re.findall(r"[\u3400-\u9fff]", alias))
    latin_length = len(re.findall(r"[a-z0-9]", alias.casefold()))
    return cjk_length >= 3 or latin_length >= 6


def _text_contains_alias(text: str, alias: str) -> bool:
    if not text or not alias:
        return False
    if re.search(r"[\u3400-\u9fff]", alias):
        return alias in text
    escaped = re.escape(alias.casefold())
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text.casefold()))


def _structured_values(article: dict[str, Any]) -> list[tuple[str, str, float]]:
    values: list[tuple[str, str, float]] = []
    company = clean(article.get("company"), 200)
    if company and company not in GENERIC_COMPANIES:
        values.append((company, "structured-company", 0.97))
    mentioned = article.get("mentionedCompanies")
    if isinstance(mentioned, list):
        for value in mentioned:
            item = clean(value, 200)
            if item:
                values.append((item, "mentioned-company", 0.95))
    return values


def _add_match(
    matches: dict[str, dict[str, Any]],
    entity: CompanyEntity,
    method: str,
    confidence: float,
) -> None:
    current = matches.get(entity.slug)
    if current and float(current["confidence"]) >= confidence:
        return
    matches[entity.slug] = {
        "slug": entity.slug,
        "method": method,
        "confidence": round(confidence, 2),
    }


def resolve_article(
    raw: dict[str, Any],
    registry: CompanyRegistry,
) -> tuple[dict[str, Any], bool]:
    article = copy.deepcopy(raw)
    matches: dict[str, dict[str, Any]] = {}

    explicit_slugs: list[str] = []
    if isinstance(article.get("companySlugs"), list):
        explicit_slugs.extend(clean(value, 100) for value in article["companySlugs"])
    explicit_slugs.append(clean(article.get("companySlug"), 100))
    for slug in explicit_slugs:
        entity = registry.by_slug.get(slug)
        if entity:
            _add_match(matches, entity, "explicit-slug", 1.0)

    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    source_host = normalized_host(source.get("url"))
    for entity in _entities_for_host(source_host, registry):
        _add_match(matches, entity, "official-domain", 0.99)

    for value, method, confidence in _structured_values(article):
        entity = _unique_alias_entity(value, registry)
        if entity:
            _add_match(matches, entity, method, confidence)

    accepted = sorted(
        matches.values(),
        key=lambda item: (
            -float(item["confidence"]),
            registry.by_slug[item["slug"]].order,
        ),
    )
    accepted_slugs = [item["slug"] for item in accepted]

    text = " ".join(
        [clean(article.get("title"), 500), clean(article.get("summary"), 2000)]
    )
    candidate_slugs: list[str] = []
    for alias_key, entities in registry.by_alias.items():
        if len(entities) != 1:
            continue
        entity = entities[0]
        if entity.slug in matches:
            continue
        aliases = [alias for alias in entity.aliases if normalize_identity(alias) == alias_key]
        if any(_safe_text_alias(alias) and _text_contains_alias(text, alias) for alias in aliases):
            candidate_slugs.append(entity.slug)
    candidate_slugs = sorted(
        set(candidate_slugs), key=lambda slug: registry.by_slug[slug].order
    )

    if accepted_slugs:
        article["companySlugs"] = accepted_slugs
        article["companySlug"] = accepted_slugs[0]
        article["companyMatches"] = accepted
        article["companyMatch"] = accepted[0]
        if len(accepted_slugs) == 1 and clean(article.get("company")) in GENERIC_COMPANIES:
            article["company"] = registry.by_slug[accepted_slugs[0]].name
    else:
        article.pop("companySlugs", None)
        article.pop("companySlug", None)
        article.pop("companyMatches", None)
        article.pop("companyMatch", None)

    if candidate_slugs:
        article["companyCandidateSlugs"] = candidate_slugs
    else:
        article.pop("companyCandidateSlugs", None)

    return article, article != raw


def resolve_payload(
    payload: dict[str, Any],
    registry: CompanyRegistry | None = None,
) -> tuple[dict[str, Any], dict[str, int]]:
    active_registry = registry or load_registry()
    result = copy.deepcopy(payload)
    changed_articles = 0
    resolved_articles = 0
    candidate_only_articles = 0
    articles: list[dict[str, Any]] = []

    for raw in payload.get("articles", []):
        if not isinstance(raw, dict):
            continue
        resolved, changed = resolve_article(raw, active_registry)
        articles.append(resolved)
        changed_articles += int(changed)
        resolved_articles += int(bool(resolved.get("companySlugs")))
        candidate_only_articles += int(
            bool(resolved.get("companyCandidateSlugs"))
            and not bool(resolved.get("companySlugs"))
        )

    result["articles"] = articles
    result["articleCount"] = len(articles)
    return result, {
        "changedArticles": changed_articles,
        "resolvedArticles": resolved_articles,
        "candidateOnlyArticles": candidate_only_articles,
    }


def main() -> int:
    if not ARTICLES_PATH.exists() or not REGISTRY_PATH.exists():
        raise SystemExit("article snapshot or official company registry is missing")
    payload = json.loads(ARTICLES_PATH.read_text(encoding="utf-8"))
    resolved, report = resolve_payload(payload)
    if report["changedArticles"]:
        resolved["generatedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
        ARTICLES_PATH.write_text(
            json.dumps(resolved, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
