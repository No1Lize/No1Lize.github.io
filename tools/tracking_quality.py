"""Quality scoring and near-duplicate clustering for user-managed tracking sources."""

from __future__ import annotations

import hashlib
import re
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Iterable
from urllib.parse import urlsplit

USER_SOURCE_PREFIXES = ("user-source-", "user-track-", "user-x-")
SOURCE_LEVEL_SCORES = {
    "监管文件": 36,
    "官方披露": 34,
    "原始材料": 31,
    "数据库记录": 24,
    "媒体报道": 19,
    "待交叉验证": 9,
}
GENERIC_TERMS = {
    "ai", "agi", "ai / agi", "人工智能", "技术", "科技", "公司", "企业", "行业", "产业",
    "研究", "论文", "新闻", "资讯", "产品", "项目", "模型", "系统", "平台", "创新", "投资",
    "融资", "上市", "发布", "突破", "发展", "市场", "应用", "机器人", "半导体", "新能源",
    "生物科技", "量子计算", "商业航天", "web3", "新材料", "智能制造", "tech", "technology",
    "company", "industry", "research", "paper", "news", "product", "project", "model", "system",
    "platform", "innovation", "investment", "funding", "launch", "update",
}
EVENT_TERMS = {
    "发布", "推出", "上线", "开源", "融资", "投资", "收购", "并购", "合作", "签署", "获批",
    "上市", "量产", "交付", "突破", "论文", "研究", "财报", "营收", "launch", "release",
    "open source", "funding", "investment", "acquire", "acquisition", "partnership", "approve",
    "ipo", "production", "deliver", "breakthrough", "paper", "earnings",
}
MARKETING_TERMS = {
    "重磅", "震撼", "颠覆", "引领未来", "未来已来", "赋能千行百业", "全网首发", "限时", "优惠",
    "购买", "报名", "招商", "加盟", "top 10", "best ", "sponsored", "partner content",
    "advertorial", "press release distribution",
}
TRUSTED_HOST_SUFFIXES = (".gov", ".gov.cn", ".edu", ".edu.cn")
TRUSTED_HOSTS = {
    "sec.gov", "arxiv.org", "openalex.org", "github.com", "nature.com", "science.org",
    "openai.com", "anthropic.com", "x.ai",
}
STOP_TOKENS = {
    "the", "a", "an", "and", "or", "to", "of", "for", "in", "on", "with", "from", "at", "by",
    "is", "are", "new", "announces", "announce", "launches", "launch", "releases", "release",
    "发布", "宣布", "推出", "上线", "最新", "公司",
}


def _clean(value: Any, limit: int = 500) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def _unique(values: Iterable[Any], limit: int = 80) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, 120)
        key = item.casefold()
        if not item or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _source_id(article: dict[str, Any]) -> str:
    return _clean(article.get("sourceId"), 120)


def is_user_article(article: dict[str, Any]) -> bool:
    return _source_id(article).startswith(USER_SOURCE_PREFIXES)


def _spec_index(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in ("feeds", "publicDiscovery", "papers", "xProfiles"):
        for raw in config.get(group, []):
            if isinstance(raw, dict) and raw.get("id"):
                result[str(raw["id"])] = raw
    return result


def _meaningful_terms(spec: dict[str, Any], article: dict[str, Any]) -> list[str]:
    sector = _clean(spec.get("sector") or article.get("sector"), 80).casefold()
    values: list[Any] = [
        *spec.get("keywords", []),
        spec.get("company"),
        spec.get("ticker"),
        spec.get("name"),
        spec.get("handle"),
        article.get("company"),
    ]
    result: list[str] = []
    for term in _unique(values, 80):
        normalized = term.casefold().lstrip("@")
        compact = re.sub(r"[\s/_-]+", " ", normalized).strip()
        if (
            not compact
            or compact == sector
            or compact in GENERIC_TERMS
            or len(re.sub(r"[^a-z0-9\u3400-\u9fff]", "", compact)) < 2
        ):
            continue
        result.append(term)
    return _unique(result, 40)


def _contains(text: str, term: str) -> bool:
    normalized_text = text.casefold()
    normalized_term = term.casefold().lstrip("@").strip()
    return bool(normalized_term and normalized_term in normalized_text)


def _authority_score(article: dict[str, Any]) -> int:
    source = article.get("source", {})
    level = _clean(source.get("level"), 40)
    score = SOURCE_LEVEL_SCORES.get(level, 12)
    host = (urlsplit(_clean(source.get("url"), 500)).hostname or "").lower().removeprefix("www.")
    if host in TRUSTED_HOSTS or any(host.endswith(suffix) for suffix in TRUSTED_HOST_SUFFIXES):
        score += 10
    elif host.endswith(".org"):
        score += 3
    return score


def score_tracking_article(
    article: dict[str, Any],
    spec: dict[str, Any] | None,
) -> tuple[int, list[str], bool]:
    spec = spec or {}
    title = _clean(article.get("title"), 300)
    summary = _clean(article.get("summary"), 700)
    combined = f"{title} {summary}".casefold()
    terms = _meaningful_terms(spec, article)
    title_hits = [term for term in terms if _contains(title, term)]
    body_hits = [term for term in terms if term not in title_hits and _contains(summary, term)]
    identity_values = _unique(
        [spec.get("company"), spec.get("ticker"), spec.get("name"), spec.get("handle"), article.get("company")],
        12,
    )
    identity_hits = [term for term in identity_values if _contains(title, term)]

    score = _authority_score(article)
    score += min(38, 15 * len(title_hits))
    score += min(18, 6 * len(body_hits))
    score += min(14, 7 * len(identity_hits))

    event_hits = [term for term in EVENT_TERMS if term in combined]
    if event_hits:
        score += min(10, 4 + 2 * len(event_hits))

    marketing_hits = [term for term in MARKETING_TERMS if term in combined]
    score -= min(24, 8 * len(marketing_hits))
    if len(summary) < 40:
        score -= 4
    if len(title) < 12:
        score -= 3

    source_id = _source_id(article)
    is_x = source_id.startswith("user-x-")
    relevant = bool(title_hits or body_hits or identity_hits)
    if is_x and (spec.get("handle") or spec.get("name")):
        relevant = relevant or bool(title)

    signals: list[str] = []
    if title_hits:
        signals.append(f"标题命中 {len(title_hits)} 个追踪词")
    if body_hits:
        signals.append(f"摘要命中 {len(body_hits)} 个追踪词")
    if identity_hits:
        signals.append("标题命中公司/账号")
    if event_hits:
        signals.append("包含明确事件动作")
    if marketing_hits:
        signals.append(f"营销措辞惩罚 {len(marketing_hits)} 项")
    if not relevant:
        signals.append("未命中有效追踪词")
    return max(0, min(100, score)), signals, relevant


def _article_rank(article: dict[str, Any]) -> tuple[int, int, int, str]:
    return (
        _authority_score(article),
        int(article.get("qualityScore", 0)),
        int(article.get("importance", 0)),
        _clean(article.get("publishedAt"), 20),
    )


def _date_ordinal(value: Any) -> int | None:
    raw = _clean(value, 20)
    try:
        return date.fromisoformat(raw[:10]).toordinal()
    except ValueError:
        return None


def _title_tokens(title: Any) -> set[str]:
    text = _clean(title, 300).casefold()
    tokens: set[str] = set()
    for english in re.findall(r"[a-z0-9][a-z0-9._+-]*", text):
        if english not in STOP_TOKENS and len(english) >= 2:
            tokens.add(english)
    for segment in re.findall(r"[\u3400-\u9fff]{2,}", text):
        if segment not in STOP_TOKENS:
            tokens.add(segment)
        if len(segment) >= 4:
            tokens.update(segment[index : index + 2] for index in range(len(segment) - 1))
    return tokens


def _normalized_title(title: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _clean(title, 300).casefold())


def _same_event(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not (is_user_article(left) or is_user_article(right)):
        return False
    if _clean(left.get("sector"), 80) != _clean(right.get("sector"), 80):
        return False

    left_day = _date_ordinal(left.get("publishedAt"))
    right_day = _date_ordinal(right.get("publishedAt"))
    if left_day is not None and right_day is not None and abs(left_day - right_day) > 3:
        return False

    left_title = _normalized_title(left.get("title"))
    right_title = _normalized_title(right.get("title"))
    if not left_title or not right_title:
        return False
    sequence = SequenceMatcher(None, left_title, right_title).ratio()

    left_tokens = _title_tokens(left.get("title"))
    right_tokens = _title_tokens(right.get("title"))
    union = left_tokens | right_tokens
    jaccard = len(left_tokens & right_tokens) / len(union) if union else 0.0

    left_company = _clean(left.get("company"), 100).casefold()
    right_company = _clean(right.get("company"), 100).casefold()
    same_company = (
        bool(left_company)
        and bool(right_company)
        and left_company not in {"未识别", "unknown"}
        and left_company == right_company
    )
    return sequence >= 0.9 or jaccard >= 0.76 or (same_company and sequence >= 0.72 and jaccard >= 0.45)


def _source_snapshot(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source", {})
    return {
        "name": _clean(source.get("name"), 120),
        "url": _clean(source.get("url"), 500),
        "level": _clean(source.get("level"), 40),
        "platform": _clean(source.get("platform"), 80),
        "title": _clean(article.get("title"), 300),
        "publishedAt": _clean(article.get("publishedAt"), 20),
    }


def _merge_related(representative: dict[str, Any], duplicate: dict[str, Any]) -> None:
    related = list(representative.get("relatedSources", []))
    related.extend(duplicate.get("relatedSources", []))
    related.append(_source_snapshot(duplicate))
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in related:
        url = _clean(item.get("url"), 500)
        key = url.casefold() or f"{item.get('name')}|{item.get('title')}"
        if not key or key in seen:
            continue
        unique.append(item)
        seen.add(key)
    representative["relatedSources"] = unique[:8]
    representative["duplicateCount"] = len(unique)
    fingerprint = "|".join(
        [
            _clean(representative.get("sector"), 80),
            _clean(representative.get("company"), 100),
            _normalized_title(representative.get("title"))[:120],
        ]
    )
    representative["eventClusterId"] = hashlib.sha256(fingerprint.encode("utf-8")).hexdigest()[:16]


def apply_tracking_quality(
    articles: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    minimum_score: int = 31,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs = _spec_index(config)
    accepted: list[dict[str, Any]] = []
    rejected = 0
    scored = 0

    for raw in articles:
        article = dict(raw)
        if not is_user_article(article):
            accepted.append(article)
            continue

        scored += 1
        spec = specs.get(_source_id(article))
        score, signals, relevant = score_tracking_article(article, spec)
        article["qualityScore"] = score
        article["qualitySignals"] = signals
        article["qualityStatus"] = "高可信" if score >= 65 else "可用" if score >= 45 else "低可信"

        is_x = _source_id(article).startswith("user-x-")
        source_level = _clean(article.get("source", {}).get("level"), 40)
        should_reject = (
            not is_x
            and source_level == "待交叉验证"
            and (not relevant or score < minimum_score)
        )
        if should_reject:
            rejected += 1
            continue
        accepted.append(article)

    ranked = sorted(accepted, key=_article_rank, reverse=True)
    representatives: list[dict[str, Any]] = []
    clustered = 0
    for article in ranked:
        duplicate_of = next((candidate for candidate in representatives if _same_event(candidate, article)), None)
        if duplicate_of is None:
            representatives.append(article)
            continue
        _merge_related(duplicate_of, article)
        clustered += 1

    representatives.sort(
        key=lambda item: (
            _clean(item.get("publishedAt"), 20),
            int(item.get("importance", 0)),
            int(item.get("qualityScore", 0)),
            _clean(item.get("id"), 120),
        ),
        reverse=True,
    )
    report = {
        "scoredUserArticles": scored,
        "acceptedUserArticles": scored - rejected,
        "rejectedUserArticles": rejected,
        "clusteredDuplicates": clustered,
        "minimumScore": minimum_score,
    }
    return representatives, report
