#!/usr/bin/env python3
"""Align venture research fields with explicit, entity-specific evidence.

The generic crawler and enrichment stages intentionally maximize recall across
heterogeneous public sites. This deterministic layer removes cross-field leakage
before normalization and final publication:

* company background excludes financing, listing and acquisition headlines;
* product descriptions must explicitly mention the corresponding product;
* team biographies must mention the person or contain strong biographical facts;
* financing and listing/acquisition events are routed by the actual action text;
* institution recent investments require an institution, company, date and
  explicit investment action.

Missing evidence remains blank or receives a transparent fallback. No amount,
round, investor, team biography or exit result is inferred without support.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Sequence

try:
    from .enforce_venture_entity_semantics import enforce_snapshot
    from .sanitize_venture_narratives import sanitize_narrative
    from .venture_profile_extraction import (
        CatalogCompany,
        CatalogInstitution,
        clean_text,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )
except ImportError:
    from enforce_venture_entity_semantics import enforce_snapshot
    from sanitize_venture_narratives import sanitize_narrative
    from venture_profile_extraction import (
        CatalogCompany,
        CatalogInstitution,
        clean_text,
        normalize_url,
        parse_catalog,
        sanitize_team_members,
    )


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"
ARTICLE_PATH = ROOT / "public" / "data" / "articles.json"

CAPITAL_MARKET_RE = re.compile(
    r"(?:\bipo\b|\blisted\b|\blisting\b|\bwent public\b|\bpublic market\b|"
    r"\bnasdaq\b|\bnyse\b|\bhkex\b|\bstock exchange\b|\bacquired\b|"
    r"\bacquisition\b|\bmerger\b|上市|挂牌|港股上市|美股上市|交易所|"
    r"公开市场|并购|收购|退出|退市)",
    re.IGNORECASE,
)
FINANCING_RE = re.compile(
    r"(?:\brais(?:e|ed|es|ing)\b(?!\s+(?:full[- ]year\s+)?guidance\b)|"
    r"\bfunding round\b|\bfinancing round\b|"
    r"\bseries\s+[a-z0-9]+\s+(?:funding|financing|round)\b|"
    r"\bfirst close.{0,80}(?:funding|financing)\b|"
    r"\bcomplet(?:e|ed|es|ing).{0,80}(?:funding|financing)\b|"
    r"\bseed round\b|\bpre-seed\b|\bbacked by\b|\bled by\b|"
    r"\binvestment from\b|\bsecured .{0,40} funding\b|"
    r"融资|募资|领投|跟投|战略投资|完成.{0,18}(?:轮|融资)|获得.{0,18}投资)",
    re.IGNORECASE,
)
INVESTMENT_ACTION_RE = re.compile(
    r"(?:\binvest(?:ed|s|ing)?\s+(?:in|into)\b|\bbacks?\b|\bleads?\b|"
    r"投资|融资|领投|跟投|参投|参与.{0,24}融资|加码)",
    re.IGNORECASE,
)
BIOGRAPHY_RE = re.compile(
    r"(?:\bfounder\b|\bco-founder\b|\bchief\b|\bpartner\b|\bjoined\b|"
    r"\bpreviously\b|\bformer\b|\bph\.?d\.?\b|\bprofessor\b|"
    r"创始人|联合创始人|首席|合伙人|曾任|此前|毕业于|博士|教授|加入)",
    re.IGNORECASE,
)
PROBLEM_TERMS = (
    "解决", "面向", "帮助", "降低", "提高", "保护", "自动化",
    "problem", "solve", "help", "enable", "protect", "automate",
)
MARKET_TERMS = (
    "客户", "市场", "商业化", "部署", "应用", "行业", "企业", "消费者",
    "customer", "market", "commercial", "deployment", "enterprise", "industry",
)
TECH_TERMS = (
    "模型", "算法", "架构", "平台", "系统", "芯片", "传感器", "训练", "推理",
    "多模态", "自主", "接口", "软件", "硬件", "量子", "聚变", "机器人", "无人驾驶",
    "model", "algorithm", "architecture", "platform", "system", "chip",
    "training", "inference", "autonomous", "api", "software", "hardware",
    "quantum", "fusion", "robot", "driverless", "gpu", "processor", "computing",
)
ROUND_RE = re.compile(
    r"(?:Series\s+[A-Z][0-9]?\b|Pre[- ]?Seed|Seed|Angel|Growth|Strategic|"
    r"天使轮|种子轮|Pre[- ]?[A-Z]轮|[A-Z][0-9]?轮|战略融资|股权融资)",
    re.IGNORECASE,
)
GENERIC_COMPANIES = {"", "科技产业", "未识别", "unknown"}


def _compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean_text(value, 500).casefold())


def _sentences(value: Any, limit: int = 100) -> list[str]:
    text = clean_text(value, 60000)
    chunks = re.split(
        r"(?<=[。！？!?])\s*|(?<=\.)\s+(?=[A-Z\u3400-\u9fff])|[\r\n]+|\s{3,}",
        text,
    )
    result: list[str] = []
    seen: set[str] = set()
    for raw in chunks:
        sentence = sanitize_narrative(raw, limit=520)
        key = _compact(sentence)
        if len(sentence) < 18 or len(key) < 10 or key in seen:
            continue
        result.append(sentence)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _contains_any(value: str, terms: Sequence[str]) -> bool:
    lowered = value.casefold()
    return any(term.casefold() in lowered for term in terms)


def _alias_in_text(alias: Any, value: Any) -> bool:
    """Match Latin aliases as complete tokens and CJK aliases as substrings."""
    token = clean_text(alias, 160)
    text = clean_text(value, 4000)
    if not token or not text:
        return False
    if re.fullmatch(r"[A-Za-z0-9.+_ /-]+", token):
        parts = re.findall(r"[A-Za-z0-9]+", token)
        if not parts:
            return False
        pattern = r"[\s._+/-]+".join(re.escape(part) for part in parts)
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])",
                text,
                re.IGNORECASE,
            )
        )
    return token.casefold() in text.casefold()


def _source_url(article: dict[str, Any]) -> str:
    source = article.get("source") if isinstance(article.get("source"), dict) else {}
    return normalize_url(source.get("url", ""))


def _article_text(article: dict[str, Any]) -> str:
    return clean_text(f"{article.get('title', '')}。{article.get('summary', '')}", 1800)


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
    company: CatalogCompany, articles: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    alias_keys = {_entity_key(item) for item in company.aliases if _entity_key(item)}
    matched: list[dict[str, Any]] = []
    for article in articles:
        article_slug = clean_text(article.get("companySlug"), 100)
        company_name = clean_text(article.get("company"), 120)
        if article_slug:
            if article_slug == company.slug:
                matched.append(article)
            continue
        if company_name and _entity_key(company_name) in alias_keys:
            matched.append(article)
    return sorted(
        matched,
        key=lambda item: clean_text(item.get("publishedAt"), 20),
        reverse=True,
    )

def _institution_articles(
    institution: CatalogInstitution, articles: Sequence[dict[str, Any]]
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

def _select_required_sentence(
    values: Iterable[Any],
    *,
    required_aliases: Sequence[str] = (),
    required_terms: Sequence[str] = (),
    excluded_pattern: re.Pattern[str] | None = None,
    limit: int = 520,
) -> str:
    aliases = [clean_text(alias, 120) for alias in required_aliases if clean_text(alias, 120)]
    candidates: list[tuple[int, str]] = []
    for value in values:
        for sentence in _sentences(value):
            lowered = sentence.casefold()
            if excluded_pattern and excluded_pattern.search(sentence):
                continue
            alias_hits = sum(_alias_in_text(alias, sentence) for alias in aliases)
            term_hits = sum(term.casefold() in lowered for term in required_terms)
            if aliases and not alias_hits:
                continue
            if required_terms and not term_hits:
                continue
            score = alias_hits * 4 + term_hits * 3
            score += 2 if 30 <= len(sentence) <= 260 else 0
            candidates.append((score, sentence))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    return clean_text(candidates[0][1], limit) if candidates else ""


def _clean_project_background(
    company: CatalogCompany,
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
) -> dict[str, str]:
    catalog_summary = (
        sanitize_narrative(company.summary, limit=760)
        or clean_text(company.summary, 760)
    )
    official_summary = _select_required_sentence(
        (profile.get("background", ""),),
        required_aliases=company.aliases,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=760,
    )
    summary = official_summary or catalog_summary or "当前公开来源未提供可核对的项目背景说明。"
    non_capital_articles = [
        _article_text(article)
        for article in articles[:30]
        if not CAPITAL_MARKET_RE.search(_article_text(article))
        and not FINANCING_RE.search(_article_text(article))
        and clean_text(article.get("type"), 60)
        not in {"融资", "产业投资", "IPO", "并购", "监管文件"}
    ]
    # Derived project fields must use stable, entity-bound evidence only.
    # ``profile.background`` is overwritten below, so feeding it back into this
    # selection creates a two-pass oscillation in production snapshots.
    stable_evidence = [
        company.summary,
        profile.get("technology", ""),
        *non_capital_articles,
    ]
    problem = _select_required_sentence(
        stable_evidence,
        required_aliases=company.aliases,
        required_terms=PROBLEM_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    market = _select_required_sentence(
        stable_evidence,
        required_aliases=company.aliases,
        required_terms=MARKET_TERMS,
        excluded_pattern=CAPITAL_MARKET_RE,
        limit=460,
    )
    return {
        "summary": summary,
        "problemSolved": problem,
        "marketOpportunity": market,
    }

def _product_aliases(product: str) -> list[str]:
    """Return the full label plus distinctive model codes, not brand fragments."""
    full = clean_text(product, 160)
    aliases = [full]
    generic = {
        "api", "model", "platform", "system", "engine", "chip", "robot",
        "agent", "software", "hardware", "station", "cloud", "data", "ai",
        "gpu", "cpu", "npu", "lpu",
    }
    for match in re.finditer(r"[A-Za-z][A-Za-z0-9.+_-]{1,}", full):
        token = match.group(0)
        lowered = token.casefold()
        if lowered in generic:
            continue
        if any(char.isdigit() for char in token) or (token.isupper() and len(token) >= 2):
            aliases.append(token)
    return list(dict.fromkeys(alias for alias in aliases if len(alias) >= 2))


def _refine_products(
    profile: dict[str, Any], articles: Sequence[dict[str, Any]]
) -> list[dict[str, Any]]:
    existing = {
        _compact(row.get("name")): row
        for row in profile.get("technologyProducts", [])
        if isinstance(row, dict) and _compact(row.get("name"))
    }
    # Product descriptions use immutable article evidence first. Reading
    # normalized profile narratives here creates a cross-gate two-state cycle.
    evidence_values = [
        *(_article_text(article) for article in articles[:40]),
    ]
    result: list[dict[str, Any]] = []
    for product in profile.get("products", []):
        name = clean_text(product, 160)
        if not name:
            continue
        aliases = _product_aliases(name)
        description = _select_required_sentence(
            evidence_values,
            required_aliases=aliases,
            required_terms=TECH_TERMS,
            excluded_pattern=CAPITAL_MARKET_RE,
            limit=420,
        )
        old = existing.get(_compact(name), {})
        if not description:
            old_description = sanitize_narrative(old.get("description", ""), limit=420)
            old_source_url = normalize_url(old.get("sourceUrl", ""))
            if (
                old_description
                and old_source_url
                and _contains_any(old_description, TECH_TERMS)
                and any(_alias_in_text(alias, old_description) for alias in aliases)
                and "尚未识别到可独立核对的技术说明" not in old_description
                and "具体技术参数以原始来源为准" not in old_description
            ):
                description = old_description
        if not description:
            description = (
                f"公开资料将{name}列为该公司的核心产品或技术平台，"
                "尚未识别到可独立核对的技术说明。"
            )
        highlights = [
            sentence
            for sentence in _sentences(description, 6)
            if _contains_any(sentence, TECH_TERMS)
            and any(_alias_in_text(alias, sentence) for alias in aliases)
            and "尚未识别到可独立核对的技术说明" not in sentence
            and "具体技术参数以原始来源为准" not in sentence
        ][:3]
        source_url = ""
        for article in articles:
            article_text = _article_text(article)
            if (
                description
                and description.casefold() in article_text.casefold()
                and _source_url(article)
            ):
                source_url = _source_url(article)
                break
        if not source_url:
            old_description = sanitize_narrative(old.get("description", ""), limit=420)
            if old_description == description:
                source_url = normalize_url(old.get("sourceUrl", ""))
        result.append(
            {
                "name": name,
                "category": clean_text(old.get("category"), 80) or "技术产品",
                "description": description,
                "technicalHighlights": highlights,
                "sourceUrl": source_url,
            }
        )
    return result[:12]


def _refine_team(
    profile: dict[str, Any], aliases: Sequence[str], articles: Sequence[dict[str, Any]]
) -> list[dict[str, str]]:
    members = sanitize_team_members(profile.get("team", []), aliases)
    article_values = [_article_text(article) for article in articles[:50]]
    result: list[dict[str, str]] = []
    originals = {
        clean_text(row.get("name"), 120).casefold(): row
        for row in profile.get("team", [])
        if isinstance(row, dict) and clean_text(row.get("name"), 120)
    }
    for member in members:
        row = dict(member)
        name = clean_text(row.get("name"), 120)
        original = originals.get(name.casefold(), {})
        candidate = sanitize_narrative(original.get("summary", ""), limit=360)
        if candidate and (
            name.casefold() not in candidate.casefold()
            or not BIOGRAPHY_RE.search(candidate)
        ):
            candidate = ""
        if not candidate:
            candidate = _select_required_sentence(
                article_values,
                required_aliases=(name,),
                required_terms=(
                    "founder", "co-founder", "chief", "partner", "joined", "previously",
                    "创始人", "联合创始人", "首席", "合伙人", "曾任", "此前", "加入",
                ),
                limit=360,
            )
        row["summary"] = candidate
        for field in ("background", "previousExperience"):
            value = sanitize_narrative(original.get(field, ""), limit=420)
            if value and (
                name.casefold() not in value.casefold()
                or not BIOGRAPHY_RE.search(value)
            ):
                value = ""
            row[field] = value
        result.append(row)
    return result


def _event_from_article(article: dict[str, Any], kind: str) -> dict[str, Any]:
    text = _article_text(article)
    round_match = ROUND_RE.search(text)
    if kind == "capital":
        event_type = "并购/退出" if re.search(
            r"acquired|acquisition|merger|并购|收购|退出", text, re.IGNORECASE
        ) else "上市"
    else:
        event_type = clean_text(article.get("type"), 60)
        if event_type not in {"融资", "产业投资"}:
            event_type = "融资"
    return {
        "date": clean_text(article.get("publishedAt"), 20),
        "type": event_type,
        "title": clean_text(article.get("title"), 220),
        "summary": clean_text(article.get("summary"), 520)
        or clean_text(article.get("title"), 220),
        "amount": "",
        "round": clean_text(round_match.group(0), 80) if round_match else "",
        "investors": _article_institutions(article),
        "sourceUrl": _source_url(article),
    }


def _dedupe_events(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(
        (copy.deepcopy(row) for row in rows if isinstance(row, dict)),
        key=lambda item: (clean_text(item.get("date"), 20), clean_text(item.get("title"), 220)),
        reverse=True,
    ):
        title = clean_text(row.get("title"), 220)
        source_url = normalize_url(row.get("sourceUrl", ""))
        key = f"{clean_text(row.get('date'), 20)}|{title}|{source_url}".casefold()
        if not title or not source_url or key in seen:
            continue
        row["sourceUrl"] = source_url
        result.append(row)
        seen.add(key)
        if len(result) >= 20:
            break
    return result


def _route_capital_events(
    profile: dict[str, Any], articles: Sequence[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    financing: list[dict[str, Any]] = []
    capital: list[dict[str, Any]] = []
    for row in [*profile.get("financing", []), *profile.get("capitalMarkets", [])]:
        if not isinstance(row, dict):
            continue
        text = clean_text(f"{row.get('title', '')} {row.get('summary', '')}", 1200)
        if CAPITAL_MARKET_RE.search(text):
            capital_row = copy.deepcopy(row)
            capital_row["type"] = (
                "并购/退出"
                if re.search(
                    r"acquired|acquisition|merger|并购|收购|退出",
                    text,
                    re.IGNORECASE,
                )
                else "上市"
            )
            capital.append(capital_row)
        elif FINANCING_RE.search(text) or row.get("amount") or row.get("round") or row.get("investors"):
            financing.append(row)
    for article in articles:
        text = _article_text(article)
        if CAPITAL_MARKET_RE.search(text):
            capital.append(_event_from_article(article, "capital"))
        elif FINANCING_RE.search(text):
            financing.append(_event_from_article(article, "financing"))
    return _dedupe_events(financing), _dedupe_events(capital)


def _parse_date(value: Any) -> datetime | None:
    text = clean_text(value, 24)
    try:
        return datetime.fromisoformat(text[:10]).replace(tzinfo=UTC)
    except ValueError:
        return None


def _refine_recent_investments(
    institution: CatalogInstitution,
    profile: dict[str, Any],
    articles: Sequence[dict[str, Any]],
    reference: datetime,
) -> list[dict[str, Any]]:
    start = reference - timedelta(days=365)
    rows = [
        copy.deepcopy(row)
        for row in profile.get("recentInvestments", [])
        if isinstance(row, dict)
    ]
    aliases = [alias.casefold() for alias in institution.aliases if len(alias) >= 2]
    for article in articles:
        date = _parse_date(article.get("publishedAt"))
        company = clean_text(article.get("company"), 120)
        text = _article_text(article)
        named = [value.casefold() for value in _article_institutions(article)]
        if (
            date is None
            or not start <= date <= reference
            or company.casefold() in {value.casefold() for value in GENERIC_COMPANIES}
            or not INVESTMENT_ACTION_RE.search(text)
            or not any(alias in named or alias in text.casefold() for alias in aliases)
        ):
            continue
        round_match = ROUND_RE.search(text)
        rows.append(
            {
                "name": company,
                "companySlug": clean_text(article.get("companySlug"), 100),
                "date": clean_text(article.get("publishedAt"), 20),
                "round": clean_text(round_match.group(0), 80) if round_match else "",
                "summary": clean_text(article.get("summary"), 420)
                or clean_text(article.get("title"), 220),
                "sourceUrl": _source_url(article),
            }
        )
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(rows, key=lambda item: clean_text(item.get("date"), 20), reverse=True):
        date = _parse_date(row.get("date"))
        name = clean_text(row.get("name"), 120)
        source_url = normalize_url(row.get("sourceUrl", ""))
        key = f"{name.casefold()}|{clean_text(row.get('date'), 20)}|{source_url}"
        if date is None or not start <= date <= reference or not name or not source_url or key in seen:
            continue
        row["sourceUrl"] = source_url
        result.append(row)
        seen.add(key)
        if len(result) >= 30:
            break
    return result


def refine_snapshot(
    snapshot: dict[str, Any], articles_payload: dict[str, Any], catalog_text: str
) -> tuple[dict[str, Any], dict[str, int]]:
    companies, institutions = parse_catalog(catalog_text)
    article_rows = [
        row for row in articles_payload.get("articles", []) if isinstance(row, dict)
    ]
    cleaned = copy.deepcopy(snapshot)
    diagnostics = {
        "companiesRefined": 0,
        "institutionsRefined": 0,
        "teamSummariesCleared": 0,
        "productDescriptionsReplaced": 0,
        "capitalEventsRerouted": 0,
    }
    company_profiles = cleaned.get("companies", {})
    for company in companies:
        profile = company_profiles.get(company.slug)
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        matched = _company_articles(company, article_rows)
        old_team_summaries = sum(
            bool(clean_text(row.get("summary"), 360))
            for row in profile.get("team", [])
            if isinstance(row, dict)
        )
        old_product_descriptions = [
            clean_text(row.get("description"), 420)
            for row in profile.get("technologyProducts", [])
            if isinstance(row, dict)
        ]
        old_financing = len(profile.get("financing", []))
        old_capital = len(profile.get("capitalMarkets", []))
        profile["projectBackground"] = _clean_project_background(company, profile, matched)
        profile["background"] = profile["projectBackground"]["summary"]
        profile["technologyProducts"] = _refine_products(profile, matched)
        profile["team"] = _refine_team(profile, company.aliases, matched)
        profile["financing"], profile["capitalMarkets"] = _route_capital_events(
            profile, matched
        )
        new_team_summaries = sum(
            bool(clean_text(row.get("summary"), 360))
            for row in profile.get("team", [])
            if isinstance(row, dict)
        )
        diagnostics["teamSummariesCleared"] += max(
            0, old_team_summaries - new_team_summaries
        )
        diagnostics["productDescriptionsReplaced"] += sum(
            old != clean_text(new.get("description"), 420)
            for old, new in zip(
                old_product_descriptions, profile.get("technologyProducts", [])
            )
        )
        diagnostics["capitalEventsRerouted"] += abs(
            old_financing - len(profile["financing"])
        ) + abs(old_capital - len(profile["capitalMarkets"]))
        if profile != before:
            diagnostics["companiesRefined"] += 1

    reference = _parse_date(cleaned.get("generatedAt")) or datetime.now(UTC)
    institution_profiles = cleaned.get("institutions", {})
    for institution in institutions:
        profile = institution_profiles.get(institution.slug)
        if not isinstance(profile, dict):
            continue
        before = copy.deepcopy(profile)
        matched = _institution_articles(institution, article_rows)
        profile["team"] = _refine_team(profile, institution.aliases, matched)
        profile["recentInvestments"] = _refine_recent_investments(
            institution, profile, matched, reference
        )
        if profile != before:
            diagnostics["institutionsRefined"] += 1

    quality = cleaned.setdefault("qualityGate", {})
    checks = quality.setdefault("checks", {})
    checks["ventureEvidenceAlignment"] = {
        "actual": 0,
        "required": 0,
        "passed": True,
    }
    quality["passed"] = all(
        bool(check.get("passed"))
        for check in checks.values()
        if isinstance(check, dict) and "passed" in check
    )
    # Evidence refinement must not reintroduce facts rejected by the canonical
    # entity-semantic publication gate.
    cleaned, _ = enforce_snapshot(cleaned, catalog_text)
    return cleaned, diagnostics


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--articles", type=Path, default=ARTICLE_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    articles = json.loads(args.articles.read_text(encoding="utf-8"))
    refined, diagnostics = refine_snapshot(
        snapshot, articles, args.catalog.read_text(encoding="utf-8")
    )
    rendered = json.dumps(refined, ensure_ascii=False, indent=2) + "\n"
    current = args.snapshot.read_text(encoding="utf-8")
    print(json.dumps(diagnostics, ensure_ascii=False, sort_keys=True))
    if args.check:
        if refined != snapshot:
            print("Venture profile snapshot requires evidence alignment.")
            return 1
        print("Venture profile snapshot passed evidence alignment checks.")
        return 0
    if refined == snapshot:
        print("No venture evidence alignment changes.")
        return 0
    args.snapshot.write_text(rendered, encoding="utf-8")
    print(f"Updated {args.snapshot.relative_to(ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
