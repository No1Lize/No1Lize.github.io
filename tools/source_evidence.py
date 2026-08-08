"""Classify public intelligence sources by evidence grade and publication role.

Evidence grade describes factual authority.  `sourceRole` is a separate control
plane decision:

primary        -- regulator, exchange, first-party organization/person material;
corroboration  -- independent professional media/database material;
discovery      -- search indexes, automatic media discovery and other lead-only rows.

A source may be reputable and still be `discovery` when the crawler reached it
through an automatically promoted/search-only path.  This keeps recall separate
from publication privilege.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

VALID_EVIDENCE_GRADES = {"A", "B", "C", "D"}
VALID_SOURCE_ROLES = {"primary", "corroboration", "discovery"}
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
SOURCE_ROLE_LABELS = {
    "primary": "直接事实来源",
    "corroboration": "独立交叉验证来源",
    "discovery": "线索发现来源",
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
DISCOVERY_SOURCE_IDS = {
    "finance-media-index",
    "wechat-public-index",
}
DISCOVERY_SOURCE_ID_MARKERS = (
    "-bing",
    "-google-cn",
    "-google-us",
    "-toutiao",
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


def _direct_wechat(platform: Any, url: Any) -> bool:
    return _fold(platform) == "微信" and _host(url) == "mp.weixin.qq.com"


def classify_source_role(
    *,
    grade: str,
    source_id: Any = "",
    platform: Any = "",
    url: Any = "",
    source_name: Any = "",
    explicit_role: Any = "",
) -> str:
    explicit = _fold(explicit_role)
    if explicit in VALID_SOURCE_ROLES:
        return explicit

    sid = _fold(source_id)
    if sid in DISCOVERY_SOURCE_IDS:
        return "discovery"
    if sid.startswith("user-source-source-auto-media-"):
        return "discovery"
    if sid.startswith("user-track-") and not _direct_wechat(platform, url):
        return "discovery"
    if any(marker in sid for marker in DISCOVERY_SOURCE_ID_MARKERS):
        return "discovery"

    folded_name = _fold(source_name)
    folded_platform = _fold(platform)
    if _contains_any(folded_name, DISCOVERY_PLATFORM_MARKERS) or _contains_any(
        folded_platform, DISCOVERY_PLATFORM_MARKERS
    ):
        return "discovery"

    if grade in {"A", "B"}:
        return "primary"
    if grade == "C":
        return "corroboration"
    return "discovery"


def enrich_source_evidence(
    source: dict[str, Any],
    *,
    source_category: Any = "",
    source_id: Any = "",
    explicit_role: Any = "",
) -> dict[str, Any]:
    result = dict(source)
    grade = classify_source_evidence(
        level=result.get("level"),
        platform=result.get("platform"),
        url=result.get("url"),
        source_name=result.get("name"),
        source_category=source_category,
    )
    role = classify_source_role(
        grade=grade,
        source_id=source_id,
        platform=result.get("platform"),
        url=result.get("url"),
        source_name=result.get("name"),
        explicit_role=(explicit_role or result.get("sourceRole")),
    )
    result["evidenceGrade"] = grade
    result["evidenceLabel"] = EVIDENCE_GRADE_LABELS[grade]
    result["evidencePolicy"] = EVIDENCE_GRADE_POLICIES[grade]
    result["sourceRole"] = role
    result["sourceRoleLabel"] = SOURCE_ROLE_LABELS[role]
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
                source_id=article.get("sourceId", ""),
                explicit_role=article.get("sourceRole", ""),
            )
            article["sourceRole"] = article["source"]["sourceRole"]
        enriched.append(article)
    return enriched


def validate_source_evidence(source: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    grade = str(source.get("evidenceGrade") or "")
    role = str(source.get("sourceRole") or "")
    if grade and grade not in VALID_EVIDENCE_GRADES:
        errors.append("invalid:source-evidence-grade")
    if grade and not str(source.get("evidenceLabel") or "").strip():
        errors.append("missing:source-evidence-label")
    if role and role not in VALID_SOURCE_ROLES:
        errors.append("invalid:source-role")
    if role and not str(source.get("sourceRoleLabel") or "").strip():
        errors.append("missing:source-role-label")
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
