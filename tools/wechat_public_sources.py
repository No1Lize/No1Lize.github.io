from __future__ import annotations

import hashlib
import re
from typing import Any, Sequence

MAX_QUERY_TERMS = 18
EVENT_TERMS = (
    "融资", "发布", "合作", "订单", "产品", "技术", "论文", "上市", "收购", "投资",
    "funding", "launch", "partnership", "order", "product", "technology", "paper", "IPO",
)


def _unique(values: Sequence[str] | Any, limit: int) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        key = text.casefold()
        if not text or key in seen:
            continue
        result.append(text)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _person_name(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return re.sub(r"\s+@[A-Za-z0-9_]{1,30}$", "", text).strip()


def _slug(value: Any) -> str:
    text = str(value or "").casefold()
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    if ascii_slug:
        return ascii_slug[:48]
    digest = hashlib.sha1(str(value or "track").encode("utf-8")).hexdigest()[:10]
    return f"track-{digest}"


def _title(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:60] or "track"


def _quoted_terms(values: Sequence[str], limit: int = MAX_QUERY_TERMS) -> str:
    return " OR ".join(
        f'"{value.replace(chr(34), "")}"' for value in values[:limit] if value
    )


def generated_wechat_sources(
    tracks: Sequence[dict[str, Any]], tracking: Any
) -> list[dict[str, Any]]:
    """Create one independent WeChat discovery query for every enabled track."""

    sources: list[dict[str, Any]] = []
    event_query = _quoted_terms(list(EVENT_TERMS), 12)
    for track in tracks:
        companies = _unique(track.get("sampleCompanies", []), 20)
        people = _unique(
            [_person_name(value) for value in track.get("people", []) if _person_name(value)],
            20,
        )
        keywords = _unique(track.get("keywords", []), 40)
        discovery_terms = _unique(
            [*companies[:6], *people[:5], *keywords[:10], track.get("name")],
            MAX_QUERY_TERMS,
        )
        if not discovery_terms:
            continue
        query = (
            "site:mp.weixin.qq.com/s "
            f"({_quoted_terms(discovery_terms)}) ({event_query})"
        )
        source_id = f"user-track-wechat-{_slug(track.get('slug') or track.get('name'))}"
        sources.append(
            {
                "id": source_id,
                "name": f"微信公众号 · {_title(track.get('name'))}",
                "platform": "微信公众号",
                "sourceCategory": "media",
                "region": "中国",
                "sector": str(track.get("name") or "未分类"),
                "company": "",
                "ticker": "",
                "url": "https://weixin.sogou.com/",
                "query": query,
                "keywords": discovery_terms,
                "enabled": True,
                "generated": True,
                "discoveryMethod": "search-engine",
            }
        )
    return sources
