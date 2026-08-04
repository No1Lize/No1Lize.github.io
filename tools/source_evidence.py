"""Classify public intelligence sources into an explicit A-D evidence grade.

Grades describe the strength of the source for factual claims, not whether the
underlying organization is reputable in general:

A -- regulator, exchange or statutory filing source;
B -- first-party organization/person publication or original material;
C -- professional media or structured research database;
D -- discovery index, aggregation or otherwise unverified public lead.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

VALID_EVIDENCE_GRADES = {"A", "B", "C", "D"}
EVIDENCE_GRADE_LABELS = {
    "A": "监管/法定原始来源",
    "B": "主体官方/原始材料",
    "C": "专业媒体/数据库",
    "D": "待交叉验证线索",
}
EVIDENCE_GRADE_POLICIES = {
    "A": "可作为法定披露或监管事实依据",
    "B": "可作为信息主体的正式公开声明",
    "C": "作为媒体或数据库报道使用，重大资本事实宜交叉核验",
    "D": "仅用于发现线索，不应单独表述为确定事实",
}

REGULATORY_PLATFORMS = {
    "sec",
    "cninfo",
    "巨潮资讯",
    "上海证券交易所",
    "深圳证券交易所",
    "香港交易所",
    "上交所",
    "深交所",
    "交易所公告",
    "监管披露",
}
REGULATORY_HOST_SUFFIXES = (
    "sec.gov",
    "cninfo.com.cn",
    "sse.com.cn",
    "szse.cn",
    "hkexnews.hk",
)
DISCOVERY_PLATFORM_MARKERS = (
    "搜索",
    "索引",
    "聚合",
    "用户追踪",
    "bing",
    "google alerts",
    "wechat index",
    "微信公开索引",
)
OFFICIAL_PLATFORM_MARKERS = (
    "官方网站",
    "投资者关系",
    "官方账号",
    "官方公众号",
    "公司公告",
    "机构官网",
)
PROFESSIONAL_PLATFORM_MARKERS = (
    "专业媒体",
    "新闻媒体",
    "数据库",
    "openalex",
    "arxiv",
)


def _fold(value: Any) -> str:
    return str(value or "").strip().casefold()


def _host(value: Any) -> str:
    try:
        return (urlsplit(str(value or "")).hostname or "").casefold()
    except ValueError:
        return ""


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    folded_markers = (marker.casefold() for marker in markers)
    return any(marker in value for marker in folded_markers)


def classify_source_evidence(
    *,
    level: Any = "",
    platform: Any = "",
    url: Any = "",
    source_name: Any = "",
    source_category: Any = "",
) -> str:
    normalized_level = str(level or "").strip()
    folded_platform = _fold(platform)
    folded_name = _fold(source_name)
    folded_category = _fold(source_category)
    host = _host(url)

    if normalized_level == "监管文件":
        return "A"
    if folded_platform in {item.casefold() for item in REGULATORY_PLATFORMS}:
        return "A"
    if any(host == suffix or host.endswith(f".{suffix}") for suffix in REGULATORY_HOST_SUFFIXES):
        return "A"

    if normalized_level == "待交叉验证":
        return "D"
    if _contains_any(folded_platform, DISCOVERY_PLATFORM_MARKERS):
        return "D"
    if _contains_any(folded_name, DISCOVERY_PLATFORM_MARKERS):
        return "D"

    if normalized_level in {"官方披露", "原始材料"}:
        return "B"
    if folded_category in {"company", "person", "institution"} and _contains_any(
        folded_platform, OFFICIAL_PLATFORM_MARKERS
    ):
        return "B"
    if _contains_any(folded_platform, OFFICIAL_PLATFORM_MARKERS):
        return "B"

    if normalized_level in {"媒体报道", "数据库记录"}:
        return "C"
    if _contains_any(folded_platform, PROFESSIONAL_PLATFORM_MARKERS):
        return "C"

    return "D"


def enrich_source_evidence(
    source: dict[str, Any],
    *,
    source_category: Any = "",
) -> dict[str, Any]:
    result = dict(source)
    grade = classify_source_evidence(
        level=result.get("level"),
        platform=result.get("platform"),
        url=result.get("url"),
        source_name=result.get("name"),
        source_category=source_category,
    )
    result["evidenceGrade"] = grade
    result["evidenceLabel"] = EVIDENCE_GRADE_LABELS[grade]
    result["evidencePolicy"] = EVIDENCE_GRADE_POLICIES[grade]
    return result


def enrich_article_sources(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for raw in articles:
        article = dict(raw)
        source = article.get("source")
        if isinstance(source, dict):
            article["source"] = enrich_source_evidence(
                source,
                source_category=article.get("sourceCategory", ""),
            )
        enriched.append(article)
    return enriched


def validate_source_evidence(source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    grade = str(source.get("evidenceGrade") or "")
    if grade and grade not in VALID_EVIDENCE_GRADES:
        errors.append("invalid:source-evidence-grade")
    if grade and not str(source.get("evidenceLabel") or "").strip():
        errors.append("missing:source-evidence-label")
    return errors


def article_source_grade_index(article_payload: dict[str, Any]) -> dict[str, str]:
    """Return the strongest observed grade for each source ID in the snapshot."""

    rank = {"A": 4, "B": 3, "C": 2, "D": 1}
    result: dict[str, str] = {}
    articles = article_payload.get("articles", [])
    if not isinstance(articles, list):
        return result
    for article in articles:
        if not isinstance(article, dict):
            continue
        source_id = str(article.get("sourceId") or "").strip()
        source = article.get("source") if isinstance(article.get("source"), dict) else {}
        grade = str(source.get("evidenceGrade") or "")
        if not source_id or grade not in rank:
            continue
        previous = result.get(source_id)
        if previous is None or rank[grade] > rank[previous]:
            result[source_id] = grade
    return result
