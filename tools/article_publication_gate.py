"""Publication gate for low-authority discovery sources.

Collection and publication are separate privileges.  Discovery sources may scan
broadly, but their rows enter the committed public snapshot only when they carry
a concrete entity, a concrete event and strong relevance, or when an independent
primary/corroborating source confirms the same entity/event in the same window.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Iterable
from urllib.parse import urlsplit


VALID_SOURCE_ROLES = {"primary", "corroboration", "discovery"}
EXPLICIT_EVENT_TYPES = {
    "融资",
    "产业投资",
    "产品发布",
    "技术突破",
    "商业进展",
    "并购",
    "财报",
    "政策",
    "监管文件",
    "IPO",
    "论文",
}
GENERIC_COMPANIES = {
    "",
    "科技产业",
    "持续更新",
    "未识别",
    "未分类",
    "unknown",
    "公司",
    "行业",
    "产业",
    "资本动态",
}


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _fold(value: Any) -> str:
    return _clean(value).casefold()


def _source(article: dict[str, Any]) -> dict[str, Any]:
    value = article.get("source")
    return value if isinstance(value, dict) else {}


def _role(article: dict[str, Any]) -> str:
    source = _source(article)
    explicit = _fold(source.get("sourceRole") or article.get("sourceRole"))
    if explicit in VALID_SOURCE_ROLES:
        return explicit
    grade = _clean(source.get("evidenceGrade")).upper()
    if grade in {"A", "B"}:
        return "primary"
    if grade == "C":
        return "corroboration"
    return "discovery"


def _source_identity(article: dict[str, Any]) -> tuple[str, str]:
    source = _source(article)
    source_id = _fold(article.get("sourceId"))
    try:
        host = (urlsplit(_clean(source.get("url"))).hostname or "").casefold()
    except ValueError:
        host = ""
    return source_id, host


def _entity_keys(article: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    company_slug = _fold(article.get("companySlug"))
    person_slug = _fold(article.get("personSlug"))
    if company_slug:
        keys.add(f"company-slug:{company_slug}")
    if person_slug:
        keys.add(f"person-slug:{person_slug}")

    company = _clean(article.get("company"))
    if _fold(company) not in GENERIC_COMPANIES:
        keys.add(f"company:{_fold(company)}")

    for field, prefix in (
        ("mentionedCompanies", "company"),
        ("mentionedPeople", "person"),
    ):
        values = article.get(field)
        if not isinstance(values, list):
            continue
        for value in values[:12]:
            normalized = _fold(value)
            if normalized and normalized not in GENERIC_COMPANIES:
                keys.add(f"{prefix}:{normalized}")
    return keys


def _published_day(article: dict[str, Any]) -> int | None:
    raw = _clean(article.get("publishedAt"))[:10]
    try:
        return date.fromisoformat(raw).toordinal()
    except ValueError:
        return None


def _explicit_event(article: dict[str, Any]) -> bool:
    return _clean(article.get("type")) in EXPLICIT_EVENT_TYPES


def _title_mentions_entity(article: dict[str, Any]) -> bool:
    title = _fold(article.get("title"))
    if not title:
        return False
    company = _fold(article.get("company"))
    if company and company not in GENERIC_COMPANIES and company in title:
        return True
    for field in ("mentionedCompanies", "mentionedPeople"):
        values = article.get(field)
        if not isinstance(values, list):
            continue
        if any(_fold(value) and _fold(value) in title for value in values[:12]):
            return True
    return bool(article.get("companySlug") or article.get("personSlug")) and bool(
        _entity_keys(article)
    )


def _strong_relevance(article: dict[str, Any]) -> bool:
    try:
        score = int(article.get("qualityScore", -1))
    except (TypeError, ValueError):
        score = -1
    if score >= 45:
        return True
    return _explicit_event(article) and _title_mentions_entity(article)


def _independent(
    left: dict[str, Any], right: dict[str, Any]
) -> bool:
    left_id, left_host = _source_identity(left)
    right_id, right_host = _source_identity(right)
    if left_id and right_id and left_id == right_id:
        return False
    if left_host and right_host and left_host == right_host:
        return False
    return True


def _same_event(
    discovery: dict[str, Any], stronger: dict[str, Any]
) -> bool:
    left_cluster = _fold(discovery.get("eventClusterId"))
    right_cluster = _fold(stronger.get("eventClusterId"))
    if left_cluster and right_cluster and left_cluster == right_cluster:
        return _independent(discovery, stronger)
    if _clean(discovery.get("type")) != _clean(stronger.get("type")):
        return False
    if not (_entity_keys(discovery) & _entity_keys(stronger)):
        return False
    left_day = _published_day(discovery)
    right_day = _published_day(stronger)
    if left_day is not None and right_day is not None and abs(left_day - right_day) > 3:
        return False
    return _independent(discovery, stronger)


def _corroborated(
    article: dict[str, Any], stronger_articles: Iterable[dict[str, Any]]
) -> bool:
    return any(_same_event(article, stronger) for stronger in stronger_articles)


def filter_publishable_articles(
    articles: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    stronger = [article for article in articles if _role(article) != "discovery"]
    published: list[dict[str, Any]] = []
    report = {
        "total": len(articles),
        "primary": 0,
        "corroboration": 0,
        "discoverySeen": 0,
        "discoveryPublished": 0,
        "discoveryHeld": 0,
    }

    for article in articles:
        role = _role(article)
        if role == "primary":
            report["primary"] += 1
            published.append(article)
            continue
        if role == "corroboration":
            report["corroboration"] += 1
            published.append(article)
            continue

        report["discoverySeen"] += 1
        has_entity = bool(_entity_keys(article))
        has_event = _explicit_event(article)
        allowed = has_entity and has_event and (
            _strong_relevance(article) or _corroborated(article, stronger)
        )
        if allowed:
            report["discoveryPublished"] += 1
            published.append(article)
        else:
            report["discoveryHeld"] += 1

    return published, report
