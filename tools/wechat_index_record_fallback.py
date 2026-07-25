"""Create transparent index-only WeChat records when original pages are unavailable."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any


def _relative_date(value: str, crawler: Any) -> str:
    normalized = crawler.normalize_date(value)
    if normalized:
        return normalized
    text = str(value or "")
    today = datetime.now(UTC).date()
    if "昨天" in text:
        return (today - timedelta(days=1)).isoformat()
    if "前天" in text:
        return (today - timedelta(days=2)).isoformat()
    match = re.search(r"(\d+)\s*(分钟|小时|天|周|月)前", text)
    if not match:
        return today.isoformat()
    amount = int(match.group(1))
    unit = match.group(2)
    days = 0
    if unit == "天":
        days = amount
    elif unit == "周":
        days = amount * 7
    elif unit == "月":
        days = amount * 30
    return (today - timedelta(days=days)).isoformat()


def _index_summary(
    account: str,
    title: str,
    companies: list[str],
    people: list[str],
    keywords: list[str],
) -> str:
    entities = []
    for value in [*companies, *people, *keywords]:
        if value and value not in entities:
            entities.append(value)
    detail = f"，涉及{'、'.join(entities[:8])}" if entities else ""
    return (
        f"{account}的公开索引显示该账号发布《{title}》{detail}。"
        "当前仅获得标题与索引元数据，正文将在后续成功读取微信原文时补全。"
    )


def _build_index_article(
    row: dict[str, str],
    spec: dict[str, Any],
    crawler: Any,
    wechat: Any,
) -> dict[str, Any] | None:
    title = crawler.clean_title(row.get("title", ""))
    context = str(row.get("summary", ""))
    if not title or len(title) < 6:
        return None
    companies, people, keywords = wechat._relevance_entities(
        title,
        context,
        "",
        spec,
        crawler,
    )
    if not (companies or people or keywords):
        return None
    company, company_slug = wechat._company_attribution(
        title,
        context,
        str(spec.get("name", "")),
        companies,
        crawler,
    )
    summary = _index_summary(
        str(spec.get("name", "微信公众号")),
        title,
        companies,
        people,
        keywords,
    )
    article = crawler._external_article(
        spec,
        title=title,
        summary=summary,
        url=row.get("url", ""),
        published_at=_relative_date(row.get("date") or context, crawler),
        source_name=str(spec.get("name", "微信公众号")),
        source_level="数据库记录",
        platform="微信公开索引",
        company=company,
        company_slug=company_slug,
    )
    article["sector"] = spec.get("sector") or article.get("sector")
    article["wechatAccount"] = spec.get("name", "")
    if spec.get("accountConfigId"):
        article["wechatAccountConfigId"] = spec["accountConfigId"]
    article["wechatContentMode"] = "index-only"
    article["mentionedCompanies"] = companies
    article["mentionedPeople"] = people
    article["matchedTrackingTerms"] = keywords[:20]
    article["qualityScore"] = 42
    article["qualityStatus"] = "待交叉验证"
    article["qualitySignals"] = [
        "公众号名称与公开索引匹配",
        "仅获得标题与索引元数据",
        f"识别 {len(companies)} 家相关公司",
        f"识别 {len(people)} 位相关人物",
    ]
    return article


def install(wechat: Any, bridge: Any) -> None:
    """Add index-only records after all original-page fallbacks are exhausted."""

    original_crawl = wechat.crawl_wechat_source
    if getattr(original_crawl, "_wechat_index_record_fallback", False):
        return

    def crawl_wechat_source(
        spec: dict[str, Any], user_agent: str, crawler: Any
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        articles, status = original_crawl(spec, user_agent, crawler)
        if articles or not spec.get("publicIndexUrls"):
            return articles, status

        rows: list[dict[str, str]] = []
        failures = int(status.get("failed", 0) or 0)
        seen: set[str] = set()
        for index_url in spec.get("publicIndexUrls", []):
            try:
                body = bridge._fetch_cached(index_url, user_agent, crawler)
                discovered = bridge._extract_index_rows(
                    body,
                    index_url,
                    spec,
                    crawler,
                )
            except Exception:  # noqa: BLE001 - reflected in aggregate status.
                failures += 1
                continue
            for row in discovered:
                url = crawler.normalize_url(row.get("url", ""))
                if not url or url in seen:
                    continue
                rows.append({**row, "url": url})
                seen.add(url)

        accepted: list[dict[str, Any]] = []
        for row in rows:
            article = _build_index_article(row, spec, crawler, wechat)
            if article:
                accepted.append(article)
            if len(accepted) >= int(spec.get("maxItems", 6)):
                break
        if not accepted:
            return articles, status

        next_status = crawler._status(
            spec["id"],
            spec["name"],
            "partial",
            len(rows),
            len(accepted),
            failed=failures,
            platform="微信",
            error=None,
        )
        next_status["discoveryProvider"] = "public-index-metadata"
        next_status["indexOnly"] = True
        return accepted, next_status

    setattr(crawl_wechat_source, "_wechat_index_record_fallback", True)
    wechat.crawl_wechat_source = crawl_wechat_source
