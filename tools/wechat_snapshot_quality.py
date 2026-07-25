"""Final quality controls for WeChat entities and cross-sector duplicates."""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

NON_PERSON_TOKENS = {
    "agent",
    "alignment",
    "anthropic",
    "architecture",
    "asia",
    "benchmark",
    "browser",
    "chatgpt",
    "chrome",
    "claude",
    "code",
    "compiler",
    "core",
    "dataset",
    "decoding",
    "deepseek",
    "drafting",
    "engine",
    "epic",
    "facemind",
    "framework",
    "google",
    "gpt",
    "lab",
    "laboratory",
    "link",
    "loop",
    "mission",
    "model",
    "mythos",
    "openai",
    "preview",
    "protocol",
    "qbitai",
    "research",
    "runtime",
    "speculative",
    "system",
    "ultra",
}
CHINESE_NON_PERSON = {
    "论文链接",
    "研究团队",
    "项目团队",
    "作者团队",
    "技术团队",
    "公司团队",
    "首席未来",
    "开源社区",
    "研究机构",
}


def _clean(value: Any, limit: int = 160) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _clean(value).casefold())


def canonical_url(value: Any) -> str:
    text = _clean(value, 1200)
    try:
        parts = urlsplit(text)
    except ValueError:
        return text
    query = urlencode(sorted(parse_qsl(parts.query, keep_blank_values=True)))
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), parts.path, query, ""))


def is_likely_person(value: Any) -> bool:
    label = _clean(value, 100).strip(" ·•|｜-—–()（）[]【】,，:：")
    if not label:
        return False
    if re.fullmatch(r"[\u3400-\u9fff·]{2,5}", label):
        return label not in CHINESE_NON_PERSON and not any(
            token in label for token in ("团队", "公司", "机构", "链接", "论文", "模型")
        )
    if not re.fullmatch(
        r"[A-Z][A-Za-z'.-]{1,24}(?:\s+[A-Z][A-Za-z'.-]{1,24}){1,2}",
        label,
    ):
        return False
    tokens = [token.strip(".'-").casefold() for token in label.split()]
    if any(token in NON_PERSON_TOKENS for token in tokens):
        return False
    return all(len(token) >= 2 for token in tokens)


def clean_people(values: Iterable[Any], companies: Iterable[Any] = ()) -> list[str]:
    company_keys = {_key(value) for value in companies if _key(value)}
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        label = _clean(value, 100)
        key = _key(label)
        if (
            not key
            or key in seen
            or key in company_keys
            or not is_likely_person(label)
        ):
            continue
        result.append(label)
        seen.add(key)
    return result[:24]


def clean_article_entities(article: dict[str, Any]) -> dict[str, Any]:
    companies = [
        _clean(value, 100)
        for value in article.get("mentionedCompanies", [])
        if _clean(value, 100)
    ]
    article["mentionedCompanies"] = list(dict.fromkeys(companies))[:24]
    article["mentionedPeople"] = clean_people(
        article.get("mentionedPeople", []),
        [article.get("company", ""), *article["mentionedCompanies"]],
    )
    return article


def _track_maps(tracking_payload: dict[str, Any]) -> tuple[dict[str, set[str]], dict[str, list[str]]]:
    company_owners: dict[str, set[str]] = defaultdict(set)
    track_terms: dict[str, list[str]] = {}
    for track in tracking_payload.get("tracks", []):
        if not isinstance(track, dict) or track.get("enabled", True) is False:
            continue
        sector = _clean(track.get("name"), 80)
        if not sector:
            continue
        track_terms[sector] = [
            _clean(value, 80)
            for value in [sector, *track.get("keywords", [])]
            if _clean(value, 80)
        ]
        for company in track.get("sampleCompanies", []):
            key = _key(company)
            if key:
                company_owners[key].add(sector)
    return company_owners, track_terms


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    if re.fullmatch(r"[A-Za-z0-9.+#-]+", term):
        return bool(re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", text, re.I))
    return term.casefold() in text.casefold()


def _sector_score(
    article: dict[str, Any],
    company_owners: dict[str, set[str]],
    track_terms: dict[str, list[str]],
) -> int:
    sector = _clean(article.get("sector"), 80)
    title = _clean(article.get("title"), 500)
    summary = _clean(article.get("summary"), 1000)
    score = 0

    company_values = [article.get("company", ""), *article.get("mentionedCompanies", [])]
    for index, company in enumerate(company_values):
        owners = company_owners.get(_key(company), set())
        if len(owners) != 1:
            continue
        weight = 120 if index == 0 else 35
        score += weight if sector in owners else -weight

    for term in track_terms.get(sector, []):
        if _contains(title, term):
            score += 8
        elif _contains(summary, term):
            score += 2
    for term in article.get("matchedTrackingTerms", []):
        if _contains(title, _clean(term, 80)):
            score += 5
        elif _contains(summary, _clean(term, 80)):
            score += 1
    return score


def resolve_cross_sector_articles(
    articles: Sequence[dict[str, Any]],
    tracking_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Keep one best sector for the same public WeChat article URL."""

    company_owners, track_terms = _track_maps(tracking_payload)
    grouped: dict[str, list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    order: list[str] = []
    for index, raw in enumerate(articles):
        article = clean_article_entities(dict(raw))
        url = canonical_url(article.get("source", {}).get("url", ""))
        key = url or f"missing:{index}"
        if key not in grouped:
            order.append(key)
        grouped[key].append((index, article))

    result: list[dict[str, Any]] = []
    for key in order:
        candidates = grouped[key]
        selected = max(
            candidates,
            key=lambda item: (_sector_score(item[1], company_owners, track_terms), -item[0]),
        )[1]
        result.append(selected)
    return result
