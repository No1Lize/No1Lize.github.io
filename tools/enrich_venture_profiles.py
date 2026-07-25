#!/usr/bin/env python3
"""Enrich every startup and institution profile with the same research logic.

The primary crawler extracts bounded evidence from heterogeneous public websites.
This second deterministic stage connects that evidence with the public intelligence
snapshot and the production catalog. It improves concise narratives, financing and
exit timelines, recent-year institution activity and classic-case analysis without
inventing facts when a field is not publicly disclosed.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .sanitize_venture_narratives import sanitize_narrative
    from .venture_profile_extraction import (
        CatalogCompany,
        CatalogInstitution,
        clean_text,
        evidence_score,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )
except ImportError:
    from sanitize_venture_narratives import sanitize_narrative
    from venture_profile_extraction import (
        CatalogCompany,
        CatalogInstitution,
        clean_text,
        evidence_score,
        parse_catalog,
        sanitize_product_items,
        sanitize_team_members,
    )


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
PROFILE_PATH = ROOT / "public" / "data" / "venture_profiles.json"
ARTICLE_PATH = ROOT / "public" / "data" / "articles.json"
RESEARCH_MODEL_VERSION = 3

GENERIC_COMPANIES = {"", "科技产业", "未识别", "unknown"}
NAVIGATION_TERMS = (
    "首页",
    "关于我们",
    "产品中心",
    "产品资料",
    "联系我们",
    "加入我们",
    "新闻资讯",
    "解决方案",
    "privacy",
    "careers",
    "contact",
    "all rights reserved",
)
PROBLEM_TERMS = (
    "解决",
    "面向",
    "帮助",
    "降低",
    "提高",
    "保护",
    "自动化",
    "problem",
    "solve",
    "help",
    "enable",
    "protect",
    "automate",
)
MARKET_TERMS = (
    "客户",
    "市场",
    "商业化",
    "部署",
    "应用",
    "行业",
    "企业",
    "消费者",
    "customer",
    "market",
    "commercial",
    "deployment",
    "enterprise",
    "industry",
)
TECH_HIGHLIGHT_TERMS = (
    "模型",
    "算法",
    "架构",
    "平台",
    "系统",
    "芯片",
    "传感器",
    "训练",
    "推理",
    "多模态",
    "自主",
    "model",
    "algorithm",
    "architecture",
    "platform",
    "system",
    "chip",
    "training",
    "inference",
    "autonomous",
)
ROUND_PATTERN = re.compile(
    r"(?:Series\s+[A-Z][0-9]?|Pre[- ]?Seed|Seed|Angel|Growth|Strategic|"
    r"天使轮|种子轮|Pre[- ]?[A-Z]轮|[A-Z][0-9]?轮|战略融资|股权融资|IPO)",
    re.IGNORECASE,
)


def _load_json(path: Path, fallback: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback
    return value


def _sentences(value: Any, limit: int = 80) -> list[str]:
    text = clean_text(value, 60000)
    if not text:
        return []
    chunks = re.split(
        r"(?<=[。！？!?])\s*|(?<=\.)\s+(?=[A-Z\u3400-\u9fff])|[\r\n]+|\s{3,}",
        text,
    )
    result: list[str] = []
    seen: set[str] = set()
    for raw in chunks:
        sentence = clean_text(raw, 520).strip(" -|｜›→")
        compact = re.sub(r"[^A-Za-z0-9\u3400-\u9fff]+", "", sentence).casefold()
        if len(sentence) < 22 or len(compact) < 12:
            continue
        if any(term.casefold() in sentence.casefold() for term in NAVIGATION_TERMS):
            if len(sentence) > 180 or sum(
                term.casefold() in sentence.casefold() for term in NAVIGATION_TERMS
            ) >= 2:
                continue
        if compact in seen:
            continue
        result.append(sentence)
        seen.add(compact)
        if len(result) >= limit:
            break
    return result


def _navigation_heavy(value: Any) -> bool:
    text = clean_text(value, 5000)
    lowered = text.casefold()
    hits = sum(lowered.count(term.casefold()) for term in NAVIGATION_TERMS)
    return len(text) > 520 and (hits >= 4 or len(_sentences(text, 10)) <= 1)


def _select_sentences(
    values: Iterable[Any],
    aliases: Sequence[str],
    keywords: Sequence[str],
    *,
    maximum: int = 3,
    limit: int = 760,
) -> str:
    candidates: list[tuple[int, str]] = []
    alias_values = [item.casefold() for item in aliases if len(clean_text(item, 100)) >= 2]
    for value in values:
        for sentence in _sentences(value):
            lowered = sentence.casefold()
            score = sum(3 for term in keywords if term.casefold() in lowered)
            score += sum(2 for alias in alias_values if alias in lowered)
            score += 2 if 35 <= len(sentence) <= 260 else 0
            score += 1 if re.search(r"\d", sentence) else 0
            if score >= 3:
                candidates.append((score, sentence))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    chosen: list[str] = []
    keys: list[str] = []
    total = 0
    for _, sentence in candidates:
        key = re.sub(r"[^A-Za-z0-9\u3400-\u9fff]+", "", sentence).casefold()
        if not key or any(key in old or old in key for old in keys):
            continue
        if chosen and total + len(sentence) > limit:
            continue
        chosen.append(sentence)
        keys.append(key)
        total += len(sentence)
        if len(chosen) >= maximum:
            break
    return clean_text(" ".join(chosen), limit)


def _article_source_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return clean_text(source.get("url"), 1000)


def _article_institutions(article: dict[str, Any]) -> list[str]:
    values = article.get("institutions", [])
    if not isinstance(values, list):
        return []
    return [clean_text(item, 120) for item in values if clean_text(item, 120)]


def _entity_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9\u3400-\u9fff]+",
        "",
        clean_text(value, 160).casefold(),
    )

def _company_articles(
    slug: str,
    company: CatalogCompany,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in company.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        article_slug = clean_text(article.get("companySlug"), 100)
        company_name = clean_text(article.get("company"), 120)
        if article_slug:
            if article_slug == slug:
                result.append(article)
            continue
        if company_name and _entity_key(company_name) in alias_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )

def _institution_articles(
    institution: CatalogInstitution,
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in institution.aliases if _entity_key(item)}
    result: list[dict[str, Any]] = []
    for article in articles:
        named_keys = {
            _entity_key(item)
            for item in _article_institutions(article)
            if _entity_key(item)
        }
        if alias_keys & named_keys:
            result.append(article)
    return sorted(
        result,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )

def _capital_event_from_article(article: dict[str, Any]) -> dict[str, Any]:
    summary = clean_text(article.get("summary"), 520)
    round_match = ROUND_PATTERN.search(f"{article.get('title', '')} {summary}")
    return {
        "date": clean_text(article.get("publishedAt"), 20),
        "type": clean_text(article.get("type"), 60) or "资本事件",
        "title": clean_text(article.get("title"), 220),
        "summary": summary or clean_text(article.get("title"), 220),
        "amount": "",
        "round": clean_text(round_match.group(0), 80) if round_match else "",
        "investors": _article_institutions(article),
        "sourceUrl": _article_source_url(article),
    }


def _merge_events(
    existing: Any,
    articles: Sequence[dict[str, Any]],
    accepted_types: set[str],
    limit: int = 20,
) -> list[dict[str, Any]]:
    rows = [item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
    rows.extend(
        _capital_event_from_article(article)
        for article in articles
        if clean_text(article.get("type"), 60) in accepted_types
    )
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(
        rows,
        key=lambda item: (
            clean_text(item.get("date"), 20),
            clean_text(item.get("title"), 220),
        ),
        reverse=True,
    ):
        title = clean_text(row.get("title"), 220)
        summary = clean_text(row.get("summary"), 520)
        source_url = clean_text(row.get("sourceUrl"), 1000)
        key = f"{clean_text(row.get('date'), 20)}|{title}|{source_url}".casefold()
        if not title or key in seen:
            continue
        result.append(
            {
                "date": clean_text(row.get("date"), 20),
                "type": clean_text(row.get("type"), 60) or "资本事件",
                "title": title,
                "summary": summary or title,
                "amount": clean_text(row.get("amount"), 80),
                "round": clean_text(row.get("round"), 80),
                "investors": [
                    clean_text(item, 100)
                    for item in row.get("investors", [])
                    if clean_text(item, 100)
                ][:12],
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _product_category(name: str, description: str) -> str:
    text = f"{name} {description}".casefold()
    categories = (
        (("机器人", "robot"), "机器人 / 硬件"),
        (("芯片", "chip", "processor"), "芯片 / 算力"),
        (("模型", "model", "llm"), "模型"),
        (("平台", "platform"), "平台"),
        (("api", "接口"), "API / 开发工具"),
        (("系统", "system", "software", "软件"), "软件 / 系统"),
        (("服务", "service"), "服务"),
    )
    for terms, category in categories:
        if any(term in text for term in terms):
            return category
    return "技术产品"


def _technology_products(
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    products = sanitize_product_items(profile.get("products", []))
    evidence_values = [
        profile.get("researchTechnology", ""),
        profile.get("technology", ""),
        profile.get("background", ""),
        *(
            f"{article.get('title', '')}。{article.get('summary', '')}"
            for article in articles[:20]
        ),
    ]
    rows: list[dict[str, Any]] = []
    for product in products[:12]:
        description = _select_sentences(
            evidence_values,
            (product,),
            (*TECH_HIGHLIGHT_TERMS, "产品", "product"),
            maximum=1,
            limit=360,
        )
        if not description:
            description = f"公开资料将{product}列为该公司的核心产品或技术平台，具体技术参数以原始来源为准。"
        highlights = [
            sentence
            for sentence in _sentences(description, 6)
            if any(term.casefold() in sentence.casefold() for term in TECH_HIGHLIGHT_TERMS)
        ][:3]
        source_url = next(
            (
                _article_source_url(article)
                for article in articles
                if product.casefold()
                in clean_text(
                    f"{article.get('title', '')} {article.get('summary', '')}", 1600
                ).casefold()
                and _article_source_url(article)
            ),
            "",
        )
        rows.append(
            {
                "name": product,
                "category": _product_category(product, description),
                "description": description,
                "technicalHighlights": highlights,
                "sourceUrl": source_url,
            }
        )
    return rows


def _enrich_team(
    profile: dict[str, Any],
    aliases: Sequence[str],
    articles: Sequence[dict[str, Any]],
) -> list[dict[str, str]]:
    members = sanitize_team_members(profile.get("team", []), aliases)
    values = [
        f"{article.get('title', '')}。{article.get('summary', '')}"
        for article in articles[:30]
    ]
    result: list[dict[str, str]] = []
    for member in members:
        row = dict(member)
        if not clean_text(row.get("summary"), 320):
            row["summary"] = _select_sentences(
                values,
                (clean_text(row.get("name"), 120),),
                (
                    "founder",
                    "co-founder",
                    "chief",
                    "partner",
                    "创始人",
                    "联合创始人",
                    "首席",
                    "合伙人",
                    "曾任",
                    "此前",
                ),
                maximum=1,
                limit=320,
            )
        result.append(row)
    return result


def _company_project_background(
    company: CatalogCompany,
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
) -> dict[str, str]:
    aliases = company.aliases
    article_values = [
        f"{article.get('title', '')}。{article.get('summary', '')}"
        for article in articles[:20]
    ]
    raw_background = profile.get("background", "")
    summary = _select_sentences(
        [raw_background, *article_values],
        aliases,
        (
            "founded", "mission", "company", "成立", "使命", "致力于", "总部", "研发",
        ),
        maximum=3,
        limit=760,
    )
    if not summary or _navigation_heavy(raw_background):
        summary = sanitize_narrative(company.summary, limit=760) or clean_text(company.summary, 760)
    problem = _select_sentences(
        [raw_background, profile.get("technology", ""), *article_values],
        aliases,
        PROBLEM_TERMS,
        maximum=2,
        limit=460,
    )
    market = _select_sentences(
        [raw_background, profile.get("technology", ""), *article_values],
        aliases,
        MARKET_TERMS,
        maximum=2,
        limit=460,
    )
    return {
        "summary": summary or clean_text(company.summary, 760),
        "problemSolved": problem,
        "marketOpportunity": market,
    }

def _capital_summary(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    amounts: list[str] = []
    investors: list[str] = []
    rounds: list[str] = []
    seen_amounts: set[str] = set()
    seen_investors: set[str] = set()
    seen_rounds: set[str] = set()
    for event in events:
        amount = clean_text(event.get("amount"), 80)
        round_name = clean_text(event.get("round"), 80)
        if amount and amount.casefold() not in seen_amounts:
            amounts.append(amount)
            seen_amounts.add(amount.casefold())
        if round_name and round_name.casefold() not in seen_rounds:
            rounds.append(round_name)
            seen_rounds.add(round_name.casefold())
        for investor in event.get("investors", []):
            value = clean_text(investor, 100)
            if value and value.casefold() not in seen_investors:
                investors.append(value)
                seen_investors.add(value.casefold())
    latest = events[0] if events else {}
    if events:
        summary = (
            f"共识别到{len(events)}条可追溯融资或资本投入记录。"
            f"最新记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    else:
        summary = "当前公开来源未提供可核对的融资轮次、金额和投资方记录。"
    return {
        "eventCount": len(events),
        "disclosedAmounts": amounts[:12],
        "rounds": rounds[:12],
        "majorInvestors": investors[:20],
        "latestDate": clean_text(latest.get("date"), 20),
        "latestRound": clean_text(latest.get("round"), 80),
        "summary": summary,
    }


def _exit_performance(
    company: CatalogCompany,
    events: Sequence[dict[str, Any]],
) -> dict[str, str]:
    latest = events[0] if events else {}
    event_types = " ".join(clean_text(item.get("type"), 60) for item in events).casefold()
    if "并购" in event_types or "收购" in event_types:
        status = "已发生并购或退出事件"
    elif company.status == "已上市" or "上市" in event_types or "ipo" in event_types:
        status = "已上市"
    else:
        status = "暂无公开退出信息"
    if latest:
        summary = (
            f"最新可核对资本市场记录为{clean_text(latest.get('date'), 20) or '日期未披露'}的"
            f"{clean_text(latest.get('title'), 180)}。"
        )
    elif company.status == "已上市":
        summary = "目录标记该公司已上市，尚待交易所、监管文件或公司公告补齐上市地点、代码与上市后表现。"
    else:
        summary = "当前未发现上市、并购退出或明确退出安排的可核对公开证据。"
    return {
        "status": status,
        "latestDate": clean_text(latest.get("date"), 20),
        "latestEvent": clean_text(latest.get("title"), 220),
        "summary": summary,
        "sourceUrl": clean_text(latest.get("sourceUrl"), 1000),
    }


def _parse_date(value: Any) -> datetime | None:
    text = clean_text(value, 30)
    try:
        return datetime.fromisoformat(text[:10]).replace(tzinfo=UTC)
    except ValueError:
        return None


def _portfolio_record_from_article(article: dict[str, Any]) -> dict[str, Any] | None:
    company = clean_text(article.get("company"), 120)
    if company.casefold() in {item.casefold() for item in GENERIC_COMPANIES}:
        return None
    round_match = ROUND_PATTERN.search(
        f"{article.get('title', '')} {article.get('summary', '')}"
    )
    return {
        "name": company,
        "companySlug": clean_text(article.get("companySlug"), 100),
        "date": clean_text(article.get("publishedAt"), 20),
        "round": clean_text(round_match.group(0), 80) if round_match else "",
        "summary": clean_text(article.get("summary"), 420)
        or clean_text(article.get("title"), 220),
        "sourceUrl": _article_source_url(article),
    }


def _merge_portfolio(existing: Any, additions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [item for item in existing if isinstance(item, dict)] if isinstance(existing, list) else []
    rows.extend(item for item in additions if isinstance(item, dict))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(
        rows,
        key=lambda item: clean_text(item.get("date"), 20),
        reverse=True,
    ):
        name = clean_text(row.get("name"), 120)
        if not name:
            continue
        key = f"{name.casefold()}|{clean_text(row.get('date'), 20)}"
        if key in seen:
            continue
        result.append(
            {
                "name": name,
                "companySlug": clean_text(row.get("companySlug"), 100),
                "date": clean_text(row.get("date"), 20),
                "round": clean_text(row.get("round"), 80),
                "summary": clean_text(row.get("summary"), 420) or "公开投资记录。",
                "sourceUrl": clean_text(row.get("sourceUrl"), 1000),
            }
        )
        seen.add(key)
        if len(result) >= 40:
            break
    return result


def _recent_year_summary(
    recent: Sequence[dict[str, Any]],
    articles: Sequence[dict[str, Any]],
    generated_at: str,
) -> dict[str, Any]:
    end = _parse_date(generated_at) or datetime.now(UTC)
    start = end - timedelta(days=365)
    valid = [
        row
        for row in recent
        if (parsed := _parse_date(row.get("date"))) is not None and start <= parsed <= end
    ]
    sectors: list[str] = []
    sector_seen: set[str] = set()
    for article in articles:
        parsed = _parse_date(article.get("publishedAt"))
        sector = clean_text(article.get("sector"), 100)
        if parsed is None or not start <= parsed <= end or not sector:
            continue
        if sector.casefold() not in sector_seen:
            sectors.append(sector)
            sector_seen.add(sector.casefold())
    rounds: list[str] = []
    round_seen: set[str] = set()
    for row in valid:
        value = clean_text(row.get("round"), 80)
        if value and value.casefold() not in round_seen:
            rounds.append(value)
            round_seen.add(value.casefold())
    companies = []
    company_seen: set[str] = set()
    for row in valid:
        value = clean_text(row.get("name"), 120)
        if value and value.casefold() not in company_seen:
            companies.append(value)
            company_seen.add(value.casefold())
    summary = (
        f"统计窗口为{start.date().isoformat()}至{end.date().isoformat()}，"
        f"共识别{len(valid)}条带日期的公开投资记录，涉及{len(companies)}个项目。"
    )
    return {
        "periodStart": start.date().isoformat(),
        "periodEnd": end.date().isoformat(),
        "investmentCount": len(valid),
        "companies": companies[:30],
        "sectors": sectors[:12],
        "rounds": rounds[:12],
        "summary": summary,
    }


def _classic_case_analysis(
    institution: CatalogInstitution,
    portfolio: Sequence[dict[str, Any]],
    companies: dict[str, CatalogCompany],
    company_profiles: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    ranked = sorted(
        portfolio,
        key=lambda row: (
            companies.get(clean_text(row.get("companySlug"), 100), CatalogCompany("", "", "", "", "", "", "", "", "", "", "")).status
            != "已上市",
            clean_text(row.get("date"), 20),
        ),
        reverse=False,
    )
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in ranked:
        name = clean_text(row.get("name"), 120)
        slug = clean_text(row.get("companySlug"), 100)
        if not name or name.casefold() in seen:
            continue
        company = companies.get(slug)
        company_profile = company_profiles.get(slug, {})
        if company:
            product = clean_text(company.product, 220)
            logic = (
                f"公开组合证据显示{institution.name}布局{name}；该公司位于{company.sector}赛道，"
                f"进入目录时处于{company.stage}阶段，核心产品为{product or '待公开资料补充'}。"
            )
            follow_on = _capital_summary(company_profile.get("financing", []))["summary"]
            exit_info = _exit_performance(
                company, company_profile.get("capitalMarkets", [])
            )
            exit_text = exit_info["summary"]
        else:
            logic = clean_text(row.get("summary"), 420) or (
                f"公开资料将{name}列入{institution.name}的投资组合。"
            )
            follow_on = "当前未连接到统一创业公司目录，后续融资支持和产业进展仍待补充。"
            exit_text = "当前未识别到上市或并购退出的可核对公开证据。"
        analysis = clean_text(f"{logic} {follow_on} {exit_text}", 760)
        result.append(
            {
                "name": name,
                "companySlug": slug,
                "investmentLogic": logic,
                "followOnPerformance": follow_on,
                "exitPerformance": exit_text,
                "analysis": analysis,
                "sourceUrl": clean_text(row.get("sourceUrl"), 1000),
            }
        )
        seen.add(name.casefold())
        if len(result) >= 8:
            break
    return result


def enrich_snapshot(
    snapshot: dict[str, Any],
    articles_payload: dict[str, Any],
    catalog_text: str,
) -> dict[str, Any]:
    company_specs, institution_specs = parse_catalog(catalog_text)
    company_by_slug = {item.slug: item for item in company_specs}
    institution_by_slug = {item.slug: item for item in institution_specs}
    articles = [
        item
        for item in articles_payload.get("articles", [])
        if isinstance(item, dict)
    ]
    generated_at = clean_text(snapshot.get("generatedAt"), 40) or datetime.now(UTC).replace(microsecond=0).isoformat()
    companies = snapshot.get("companies", {}) if isinstance(snapshot.get("companies"), dict) else {}
    institutions = snapshot.get("institutions", {}) if isinstance(snapshot.get("institutions"), dict) else {}

    for slug, raw_profile in companies.items():
        if not isinstance(raw_profile, dict):
            continue
        company = company_by_slug.get(slug)
        if company is None:
            continue
        matched = _company_articles(slug, company, articles)
        profile = raw_profile
        profile["background"] = sanitize_narrative(
            profile.get("background", ""),
            fallback=company.summary,
            limit=900,
        )
        profile["technology"] = sanitize_narrative(
            profile.get("technology", ""),
            fallback=company.product,
            limit=900,
        )
        project = _company_project_background(company, profile, matched)
        profile["projectBackground"] = project
        research_technology = _select_sentences(
            [
                profile.get("technology", ""),
                *(
                    f"{item.get('title', '')}。{item.get('summary', '')}"
                    for item in matched[:20]
                ),
            ],
            company.aliases,
            TECH_HIGHLIGHT_TERMS,
            maximum=3,
            limit=760,
        )
        profile["researchTechnology"] = research_technology or profile.get("technology", "")
        profile["products"] = sanitize_product_items(profile.get("products", []))
        profile["technologyProducts"] = _technology_products(profile, matched)
        profile["team"] = _enrich_team(profile, company.aliases, matched)
        profile["financing"] = _merge_events(
            profile.get("financing", []),
            matched,
            {"融资", "产业投资"},
        )
        profile["capitalMarkets"] = _merge_events(
            profile.get("capitalMarkets", []),
            matched,
            {"IPO", "并购"},
        )
        profile["capitalSummary"] = _capital_summary(profile["financing"])
        profile["exitPerformance"] = _exit_performance(
            company, profile["capitalMarkets"]
        )
        profile["researchModelVersion"] = RESEARCH_MODEL_VERSION
        profile["evidenceScore"] = evidence_score(profile, "company")

    for slug, raw_profile in institutions.items():
        if not isinstance(raw_profile, dict):
            continue
        institution = institution_by_slug.get(slug)
        if institution is None:
            continue
        matched = _institution_articles(institution, articles)
        profile = raw_profile
        profile["team"] = _enrich_team(profile, institution.aliases, matched)
        additions = [
            record
            for article in matched
            if clean_text(article.get("type"), 60) in {"融资", "产业投资"}
            if (record := _portfolio_record_from_article(article)) is not None
        ]
        profile["portfolio"] = _merge_portfolio(profile.get("portfolio", []), additions)
        end = _parse_date(generated_at) or datetime.now(UTC)
        start = end - timedelta(days=365)
        recent_additions = [
            record
            for record in additions
            if (parsed := _parse_date(record.get("date"))) is not None
            and start <= parsed <= end
        ]
        profile["recentInvestments"] = _merge_portfolio(
            profile.get("recentInvestments", []), recent_additions
        )
        profile["recentYearSummary"] = _recent_year_summary(
            profile["recentInvestments"], matched, generated_at
        )
        profile["classicCases"] = _classic_case_analysis(
            institution,
            profile["portfolio"],
            company_by_slug,
            companies,
        )
        profile["researchModelVersion"] = RESEARCH_MODEL_VERSION
        profile["evidenceScore"] = evidence_score(profile, "institution")

    result = dict(snapshot)
    result["schemaVersion"] = max(int(snapshot.get("schemaVersion", 1) or 1), 2)
    result["researchModelVersion"] = RESEARCH_MODEL_VERSION
    result["companies"] = companies
    result["institutions"] = institutions
    quality = dict(result.get("qualityGate", {})) if isinstance(result.get("qualityGate"), dict) else {}
    checks = dict(quality.get("checks", {})) if isinstance(quality.get("checks"), dict) else {}
    enriched_companies = sum(
        isinstance(item, dict)
        and isinstance(item.get("projectBackground"), dict)
        and isinstance(item.get("technologyProducts"), list)
        and isinstance(item.get("capitalSummary"), dict)
        and isinstance(item.get("exitPerformance"), dict)
        for item in companies.values()
    )
    enriched_institutions = sum(
        isinstance(item, dict)
        and isinstance(item.get("recentYearSummary"), dict)
        and isinstance(item.get("classicCases"), list)
        for item in institutions.values()
    )
    checks["companyResearchEnrichment"] = {
        "actual": enriched_companies,
        "required": len(companies),
        "passed": enriched_companies == len(companies),
    }
    checks["institutionResearchEnrichment"] = {
        "actual": enriched_institutions,
        "required": len(institutions),
        "passed": enriched_institutions == len(institutions),
    }
    quality["checks"] = checks
    quality["passed"] = all(
        bool(item.get("passed"))
        for item in checks.values()
        if isinstance(item, dict)
    )
    result["qualityGate"] = quality
    return result


def write_if_changed(path: Path, payload: dict[str, Any]) -> bool:
    serialized = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == serialized:
        print("No venture research enrichment changes.")
        return False
    path.write_text(serialized, encoding="utf-8")
    print(
        json.dumps(
            {
                "companies": len(payload.get("companies", {})),
                "institutions": len(payload.get("institutions", {})),
                "researchModelVersion": payload.get("researchModelVersion"),
                "qualityPassed": payload.get("qualityGate", {}).get("passed"),
            },
            ensure_ascii=False,
        )
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", type=Path, default=PROFILE_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    snapshot = _load_json(args.snapshot, {})
    articles = _load_json(args.articles, {"articles": []})
    catalog_text = args.catalog.read_text(encoding="utf-8")
    enriched = enrich_snapshot(snapshot, articles, catalog_text)
    if args.validate_only:
        passed = bool(enriched.get("qualityGate", {}).get("passed"))
        print(json.dumps(enriched.get("qualityGate", {}), ensure_ascii=False))
        return 0 if passed else 1
    write_if_changed(args.snapshot, enriched)
    return 0 if enriched.get("qualityGate", {}).get("passed") else 1


if __name__ == "__main__":
    raise SystemExit(main())
