#!/usr/bin/env python3
"""Deterministic extraction primitives for startup and investment profiles.

The module intentionally uses only Python's standard library.  It converts
heterogeneous public webpages into a small evidence-backed schema and keeps
all heuristics bounded, reusable and testable.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html.parser import HTMLParser
from typing import Any, Iterable, Sequence
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit


TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
    "source",
    "spm",
    "from",
}

IGNORED_TAGS = {"script", "style", "noscript", "svg", "canvas", "template"}
TEXT_TAGS = {"title", "h1", "h2", "h3", "h4", "p", "li", "blockquote"}
NAVIGATION_NOISE = {
    "home",
    "about",
    "company",
    "products",
    "product",
    "solutions",
    "news",
    "insights",
    "portfolio",
    "team",
    "people",
    "contact",
    "careers",
    "privacy",
    "terms",
    "首页",
    "关于我们",
    "产品",
    "新闻",
    "团队",
    "联系我们",
    "加入我们",
}

COMPANY_LINK_TERMS = {
    "background": ("about", "company", "mission", "story", "history", "overview", "关于", "公司", "发展历程"),
    "technology": ("technology", "research", "science", "engineering", "model", "platform", "architecture", "技术", "研发", "研究", "模型", "平台"),
    "products": ("product", "products", "solution", "solutions", "service", "services", "产品", "解决方案", "服务"),
    "team": ("team", "people", "leadership", "founder", "management", "团队", "创始人", "管理层", "领导团队"),
    "financing": ("funding", "financing", "investor", "investors", "press", "news", "融资", "投资者", "新闻", "媒体"),
    "capitalMarkets": ("investor-relations", "ir", "ipo", "listing", "stock", "sec", "hkex", "上市", "投资者关系", "公告"),
}

INSTITUTION_LINK_TERMS = {
    "overview": ("about", "firm", "company", "story", "mission", "关于", "机构", "简介"),
    "strategy": ("strategy", "thesis", "focus", "approach", "sectors", "投资策略", "投资理念", "关注领域"),
    "team": ("team", "people", "partners", "leadership", "团队", "合伙人", "管理团队"),
    "portfolio": ("portfolio", "companies", "investments", "projects", "被投企业", "投资组合", "项目"),
    "recentInvestments": ("news", "insights", "press", "updates", "investment", "新闻", "动态", "投资"),
}

BACKGROUND_KEYWORDS = (
    "founded",
    "founded in",
    "established",
    "mission",
    "company",
    "headquartered",
    "公司成立",
    "成立于",
    "总部",
    "使命",
    "致力于",
    "是一家",
)
TECHNOLOGY_KEYWORDS = (
    "technology",
    "research",
    "model",
    "architecture",
    "platform",
    "system",
    "algorithm",
    "infrastructure",
    "技术",
    "研发",
    "模型",
    "算法",
    "架构",
    "平台",
    "系统",
    "芯片",
)
PRODUCT_KEYWORDS = (
    "product",
    "products",
    "solution",
    "service",
    "platform",
    "software",
    "hardware",
    "产品",
    "解决方案",
    "服务",
    "平台",
    "软件",
    "硬件",
)
TEAM_KEYWORDS = (
    "founder",
    "co-founder",
    "chief executive",
    "ceo",
    "cto",
    "leadership",
    "partner",
    "创始人",
    "联合创始人",
    "首席执行官",
    "首席技术官",
    "董事长",
    "合伙人",
)
FINANCING_KEYWORDS = (
    "funding",
    "financing",
    "raised",
    "investment round",
    "series a",
    "series b",
    "series c",
    "valuation",
    "investor",
    "融资",
    "募资",
    "完成新一轮",
    "估值",
    "领投",
    "跟投",
    "战略投资",
)
CAPITAL_MARKET_KEYWORDS = (
    "ipo",
    "listed",
    "listing",
    "nasdaq",
    "nyse",
    "hkex",
    "stock exchange",
    "acquired",
    "acquisition",
    "merger",
    "上市",
    "挂牌",
    "交易所",
    "并购",
    "收购",
    "退出",
)
INSTITUTION_OVERVIEW_KEYWORDS = (
    "venture capital",
    "investment firm",
    "founded",
    "assets under management",
    "aum",
    "投资机构",
    "创投机构",
    "成立于",
    "管理规模",
    "基金",
)
INSTITUTION_STRATEGY_KEYWORDS = (
    "investment strategy",
    "investment thesis",
    "focus",
    "stage",
    "sector",
    "partner with founders",
    "投资策略",
    "投资理念",
    "投资阶段",
    "关注领域",
    "陪伴创业者",
)
INVESTMENT_ACTION_KEYWORDS = (
    "invested in",
    "investment in",
    "led the",
    "backs",
    "backed",
    "portfolio company",
    "funding round",
    "投资于",
    "领投",
    "参投",
    "完成融资",
    "被投企业",
)

ROLE_PATTERN = (
    r"Founder|Co[- ]Founder|Chief Executive Officer|CEO|Chief Technology Officer|CTO|"
    r"Chairman|President|Managing Partner|General Partner|Partner|"
    r"创始人|联合创始人|首席执行官|首席技术官|董事长|总裁|管理合伙人|合伙人"
)

AMOUNT_PATTERNS = (
    re.compile(r"(?:US\$|USD\s*|\$|€|£)\s?\d+(?:\.\d+)?\s?(?:million|billion|m|bn|b)?", re.IGNORECASE),
    re.compile(r"\d+(?:\.\d+)?\s?(?:亿美元|亿元|万美元|万元|亿人民币|万人民币|人民币)", re.IGNORECASE),
)
ROUND_PATTERN = re.compile(
    r"(?:Series\s+[A-Z][0-9]?|Pre[- ]?Seed|Seed|Angel|Growth|Strategic|"
    r"天使轮|种子轮|Pre[- ]?[A-Z]轮|[A-Z][0-9]?轮|战略融资|股权融资|IPO)",
    re.IGNORECASE,
)
DATE_PATTERN = re.compile(r"\b(20\d{2})[-/.年](0?[1-9]|1[0-2])(?:[-/.月](0?[1-9]|[12]\d|3[01])日?)?\b")


@dataclass(frozen=True)
class CatalogCompany:
    slug: str
    name: str
    english_name: str
    region: str
    sector: str
    stage: str
    status: str
    summary: str
    product: str
    source_name: str
    source_url: str

    @property
    def aliases(self) -> tuple[str, ...]:
        return unique_strings((self.name, self.english_name), limit=8)


@dataclass(frozen=True)
class CatalogInstitution:
    slug: str
    name: str
    english_name: str
    region: str
    institution_type: str
    stages: str
    sectors: tuple[str, ...]
    source_name: str
    source_url: str

    @property
    def aliases(self) -> tuple[str, ...]:
        aliases = [self.name, self.english_name]
        if self.slug == "a16z":
            aliases.append("a16z")
        if self.slug == "yc":
            aliases.extend(("Y Combinator", "YC"))
        return unique_strings(aliases, limit=8)


@dataclass
class ParsedPage:
    url: str
    title: str
    description: str
    blocks: list[str]
    headings: list[str]
    links: list[tuple[str, str]]
    people: list[dict[str, str]]
    published_at: str = ""
    sections: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return clean_text(" ".join([self.description, *self.blocks]), 50000)


class PublicPageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.blocks: list[str] = []
        self.headings: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._ignored_depth = 0
        self._captures: list[tuple[str, list[str]]] = []
        self._anchor: tuple[str, list[str]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.casefold()
        values = {key.casefold(): value or "" for key, value in attrs}
        if tag in IGNORED_TAGS:
            self._ignored_depth += 1
            return
        if self._ignored_depth:
            return
        if tag == "meta":
            key = clean_text(values.get("property") or values.get("name") or "", 120).casefold()
            value = clean_text(values.get("content") or "", 1200)
            if key and value:
                self.meta[key] = value
        if tag in TEXT_TAGS:
            self._captures.append((tag, []))
        if tag == "a" and values.get("href"):
            self._anchor = (values["href"], [])

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in IGNORED_TAGS:
            self._ignored_depth = max(0, self._ignored_depth - 1)
            return
        if self._ignored_depth:
            return
        for index in range(len(self._captures) - 1, -1, -1):
            capture_tag, chunks = self._captures[index]
            if capture_tag != tag:
                continue
            del self._captures[index]
            text = clean_text(" ".join(chunks), 1600)
            if text:
                self.blocks.append(text)
                if tag in {"h1", "h2", "h3", "h4"}:
                    self.headings.append(text)
            break
        if tag == "a" and self._anchor:
            href, chunks = self._anchor
            text = clean_text(" ".join(chunks), 240)
            self.links.append((href, text))
            self._anchor = None

    def handle_data(self, data: str) -> None:
        if self._ignored_depth:
            return
        for _, chunks in self._captures:
            chunks.append(data)
        if self._anchor:
            self._anchor[1].append(data)


def clean_text(value: Any, limit: int = 2000) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def unique_strings(values: Iterable[Any], limit: int = 50) -> tuple[str, ...]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in values:
        value = clean_text(raw, 300)
        key = value.casefold()
        if not value or key in seen:
            continue
        result.append(value)
        seen.add(key)
        if len(result) >= limit:
            break
    return tuple(result)


def normalize_url(url: str, base: str = "") -> str:
    absolute = urljoin(base, clean_text(url, 2000)) if base else clean_text(url, 2000)
    parts = urlsplit(absolute)
    if parts.scheme.casefold() not in {"http", "https"} or not parts.netloc:
        return ""
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        )
    )
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.casefold(), parts.netloc.casefold(), path, query, ""))


def site_domain(url: str) -> str:
    host = (urlsplit(url).hostname or "").casefold().removeprefix("www.")
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"com", "co", "org", "net"} and parts[-1] in {"cn", "uk", "au", "jp"}:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def same_site(left: str, right: str) -> bool:
    return bool(site_domain(left) and site_domain(left) == site_domain(right))


def _field(line: str, key: str) -> str:
    match = re.search(rf"\b{re.escape(key)}:\"([^\"]*)\"", line)
    return clean_text(match.group(1), 600) if match else ""


def _array_field(line: str, key: str) -> tuple[str, ...]:
    match = re.search(rf"\b{re.escape(key)}:\[([^\]]*)\]", line)
    if not match:
        return ()
    return unique_strings(re.findall(r'"([^\"]+)"', match.group(1)), limit=30)


def _source(line: str) -> tuple[str, str]:
    match = re.search(r'source:official\("([^\"]+)","([^\"]+)"\)', line)
    if not match:
        return "", ""
    return clean_text(match.group(1), 160), normalize_url(match.group(2))


def _catalog_lines(text: str, start_marker: str, end_marker: str) -> list[str]:
    start = text.find(start_marker)
    if start < 0:
        return []
    end = text.find(end_marker, start)
    block = text[start : end if end >= 0 else len(text)]
    return [line.strip() for line in block.splitlines() if "{ slug:" in line]


def parse_catalog(text: str) -> tuple[list[CatalogCompany], list[CatalogInstitution]]:
    companies: list[CatalogCompany] = []
    institutions: list[CatalogInstitution] = []

    for line in _catalog_lines(text, "export const companies", "export type Institution"):
        source_name, source_url = _source(line)
        slug = _field(line, "slug")
        name = _field(line, "name")
        if not slug or not name or not source_url:
            continue
        companies.append(
            CatalogCompany(
                slug=slug,
                name=name,
                english_name=_field(line, "englishName"),
                region=_field(line, "region"),
                sector=_field(line, "sector"),
                stage=_field(line, "stage"),
                status=_field(line, "status"),
                summary=_field(line, "summary"),
                product=_field(line, "product"),
                source_name=source_name or name,
                source_url=source_url,
            )
        )

    for line in _catalog_lines(text, "export const institutionCatalog", "export type IpoCompany"):
        source_name, source_url = _source(line)
        slug = _field(line, "slug")
        name = _field(line, "name")
        if not slug or not name or not source_url:
            continue
        institutions.append(
            CatalogInstitution(
                slug=slug,
                name=name,
                english_name=_field(line, "englishName"),
                region=_field(line, "region"),
                institution_type=_field(line, "type"),
                stages=_field(line, "stages"),
                sectors=_array_field(line, "sectors"),
                source_name=source_name or name,
                source_url=source_url,
            )
        )

    return companies, institutions


def _walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _json_ld_records(body: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for raw in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        body,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            payload = json.loads(html.unescape(raw).strip())
        except (json.JSONDecodeError, TypeError):
            continue
        records.extend(_walk_json(payload))
    return records


def _published_at(meta: dict[str, str], records: Sequence[dict[str, Any]], text: str) -> str:
    candidates = [
        meta.get("article:published_time"),
        meta.get("date"),
        meta.get("datepublished"),
        meta.get("pubdate"),
    ]
    for record in records:
        candidates.extend((record.get("datePublished"), record.get("dateCreated")))
    for candidate in candidates:
        value = clean_text(candidate, 80)
        match = re.search(r"(20\d{2})-(\d{2})-(\d{2})", value)
        if match:
            return match.group(0)
        match = DATE_PATTERN.search(value)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day or 1):02d}"
    match = DATE_PATTERN.search(text[:5000])
    if match:
        year, month, day = match.groups()
        return f"{year}-{int(month):02d}-{int(day or 1):02d}"
    return ""


def parse_public_page(url: str, body: str, kind: str) -> ParsedPage:
    parser = PublicPageParser()
    parser.feed(body)
    records = _json_ld_records(body)
    people: list[dict[str, str]] = []
    for record in records:
        record_type = record.get("@type")
        types = record_type if isinstance(record_type, list) else [record_type]
        if not any(str(item).casefold() == "person" for item in types):
            continue
        name = clean_text(record.get("name"), 120)
        role = clean_text(record.get("jobTitle") or record.get("roleName"), 160)
        description = clean_text(record.get("description"), 320)
        if name:
            people.append({"name": name, "role": role, "summary": description, "sourceUrl": url})

    title = clean_text(
        parser.meta.get("og:title")
        or parser.meta.get("twitter:title")
        or next((block for block in parser.blocks if block), ""),
        260,
    )
    description = clean_text(
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or parser.meta.get("twitter:description"),
        1200,
    )
    links = [
        (normalized, text)
        for href, text in parser.links
        if (normalized := normalize_url(href, url))
    ]
    page = ParsedPage(
        url=normalize_url(url),
        title=title,
        description=description,
        blocks=list(unique_strings(parser.blocks, limit=500)),
        headings=list(unique_strings(parser.headings, limit=120)),
        links=links,
        people=people,
    )
    page.published_at = _published_at(parser.meta, records, page.text)
    page.sections = classify_page(page, kind)
    return page


def classify_page(page: ParsedPage, kind: str) -> list[str]:
    terms = COMPANY_LINK_TERMS if kind == "company" else INSTITUTION_LINK_TERMS
    haystack = f"{page.url} {page.title} {' '.join(page.headings[:15])}".casefold()
    scored: list[tuple[int, str]] = []
    for section, keywords in terms.items():
        score = sum(2 if keyword in page.url.casefold() else 1 for keyword in keywords if keyword.casefold() in haystack)
        if score:
            scored.append((score, section))
    if not scored:
        return ["background" if kind == "company" else "overview"]
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [section for _, section in scored[:3]]


def score_discovered_links(page: ParsedPage, homepage: str, kind: str) -> list[tuple[int, str]]:
    terms = COMPANY_LINK_TERMS if kind == "company" else INSTITUTION_LINK_TERMS
    scored: dict[str, int] = {}
    for url, anchor in page.links:
        if not same_site(homepage, url):
            continue
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"}:
            continue
        text = f"{url} {anchor}".casefold()
        if any(blocked in text for blocked in ("privacy", "terms", "cookie", "login", "signin", "careers", "jobs", "mailto:")):
            continue
        score = 0
        for keywords in terms.values():
            score += sum(3 if keyword in url.casefold() else 1 for keyword in keywords if keyword.casefold() in text)
        if score:
            score += 2 if anchor and anchor.casefold() not in NAVIGATION_NOISE else 0
            scored[url] = max(score, scored.get(url, 0))
    return sorted(((score, url) for url, score in scored.items()), key=lambda item: (-item[0], item[1]))


def common_path_candidates(homepage: str, kind: str) -> list[str]:
    if kind == "company":
        paths = (
            "/about",
            "/company",
            "/team",
            "/leadership",
            "/products",
            "/technology",
            "/research",
            "/news",
            "/press",
            "/investors",
            "/investor-relations",
        )
    else:
        paths = (
            "/about",
            "/team",
            "/people",
            "/portfolio",
            "/companies",
            "/investments",
            "/news",
            "/insights",
        )
    root = urlunsplit((*urlsplit(homepage)[:2], "/", "", ""))
    return [normalize_url(path, root) for path in paths]


def split_sentences(value: str) -> list[str]:
    text = clean_text(value, 60000)
    chunks = re.split(r"(?<=[。！？!?])|(?<=\.)\s+|[\r\n]+", text)
    result: list[str] = []
    for chunk in chunks:
        sentence = clean_text(chunk, 520)
        compact = re.sub(r"[^A-Za-z0-9\u3400-\u9fff]+", "", sentence).casefold()
        if len(sentence) < 24 or len(compact) < 12:
            continue
        if compact in {re.sub(r"\W+", "", item).casefold() for item in NAVIGATION_NOISE}:
            continue
        if re.search(r"(?:privacy policy|cookie policy|all rights reserved|版权所有)", sentence, re.IGNORECASE):
            continue
        result.append(sentence)
    return list(unique_strings(result, limit=800))


def sentences_for_page(page: ParsedPage) -> list[str]:
    return split_sentences(" ".join([page.description, *page.blocks]))


def _keyword_score(sentence: str, keywords: Sequence[str], aliases: Sequence[str]) -> int:
    lowered = sentence.casefold()
    score = sum(3 for keyword in keywords if keyword.casefold() in lowered)
    score += sum(2 for alias in aliases if len(alias) >= 2 and alias.casefold() in lowered)
    if 45 <= len(sentence) <= 280:
        score += 2
    if re.search(r"\d", sentence):
        score += 1
    return score


def select_summary(
    pages: Sequence[ParsedPage],
    keywords: Sequence[str],
    aliases: Sequence[str],
    fallback: str = "",
    *,
    limit: int = 720,
) -> str:
    candidates: list[tuple[int, str]] = []
    for page in pages:
        for sentence in sentences_for_page(page):
            score = _keyword_score(sentence, keywords, aliases)
            if score >= 3:
                candidates.append((score, sentence))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    chosen: list[str] = []
    seen: set[str] = set()
    total = 0
    for _, sentence in candidates:
        key = re.sub(r"[^A-Za-z0-9\u3400-\u9fff]+", "", sentence).casefold()
        if not key or any(key in previous or previous in key for previous in seen):
            continue
        if total + len(sentence) > limit and chosen:
            continue
        chosen.append(sentence)
        seen.add(key)
        total += len(sentence)
        if len(chosen) >= 3 or total >= limit:
            break
    summary = " ".join(chosen)
    return clean_text(summary or fallback, limit)


def extract_products(pages: Sequence[ParsedPage], fallback: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for page in pages:
        for value in [page.title, *page.headings, *(text for _, text in page.links)]:
            item = clean_text(value, 220)
            lowered = item.casefold()
            if not item or len(item) < 3 or len(item) > 180:
                continue
            score = sum(2 for keyword in PRODUCT_KEYWORDS if keyword.casefold() in lowered)
            if score and lowered not in NAVIGATION_NOISE:
                candidates.append((score, item))
    for item in re.split(r"[、，,;/]|\s+与\s+|\s+and\s+", clean_text(fallback, 600), flags=re.IGNORECASE):
        item = clean_text(item, 180)
        if item:
            candidates.append((1, item))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    result: list[str] = []
    seen: set[str] = set()
    for _, item in candidates:
        key = re.sub(r"\W+", "", item).casefold()
        if not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= 10:
            break
    return result


def _valid_person_name(name: str) -> bool:
    compact = clean_text(name, 120)
    if not compact or len(compact) < 2 or len(compact) > 80:
        return False
    if compact.casefold() in NAVIGATION_NOISE:
        return False
    if re.search(r"\d|https?://|@", compact):
        return False
    return bool(re.search(r"[A-Za-z\u3400-\u9fff]", compact))


def extract_team(pages: Sequence[ParsedPage], aliases: Sequence[str]) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    for page in pages:
        members.extend(page.people)
        text = page.text
        patterns = (
            re.compile(rf"([A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){{1,3}})\s*[,|—\-]\s*({ROLE_PATTERN})", re.IGNORECASE),
            re.compile(rf"({ROLE_PATTERN})\s*[:：,，\-—]?\s*([A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){{1,3}})", re.IGNORECASE),
            re.compile(rf"([\u3400-\u9fff]{{2,5}})\s*[,，|—\-]?\s*({ROLE_PATTERN})", re.IGNORECASE),
            re.compile(rf"({ROLE_PATTERN})\s*[:：,，\-—]?\s*([\u3400-\u9fff]{{2,5}})", re.IGNORECASE),
        )
        for index, pattern in enumerate(patterns):
            for match in pattern.finditer(text):
                first, second = clean_text(match.group(1), 120), clean_text(match.group(2), 160)
                if index in {1, 3}:
                    role, name = first, second
                else:
                    name, role = first, second
                if _valid_person_name(name):
                    members.append({"name": name, "role": role, "summary": "", "sourceUrl": page.url})

    result: list[dict[str, str]] = []
    seen: set[str] = set()
    alias_keys = {alias.casefold() for alias in aliases}
    for member in members:
        name = clean_text(member.get("name"), 120)
        role = clean_text(member.get("role"), 160)
        if not _valid_person_name(name) or name.casefold() in alias_keys:
            continue
        key = name.casefold()
        if key in seen:
            existing = next(item for item in result if item["name"].casefold() == key)
            if not existing.get("role") and role:
                existing["role"] = role
            continue
        result.append(
            {
                "name": name,
                "role": role,
                "summary": clean_text(member.get("summary"), 320),
                "sourceUrl": normalize_url(member.get("sourceUrl", "")),
            }
        )
        seen.add(key)
        if len(result) >= 16:
            break
    return result


def _extract_amount(sentence: str) -> str:
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(sentence)
        if match:
            return clean_text(match.group(0), 80)
    return ""


def _extract_round(sentence: str) -> str:
    match = ROUND_PATTERN.search(sentence)
    return clean_text(match.group(0), 80) if match else ""


def _event_type(sentence: str, capital_market: bool) -> str:
    lowered = sentence.casefold()
    if capital_market:
        if any(item in lowered for item in ("acquired", "acquisition", "merger", "收购", "并购")):
            return "并购/退出"
        if any(item in lowered for item in ("ipo", "listed", "listing", "上市", "挂牌")):
            return "上市"
        return "资本市场"
    if any(item in lowered for item in ("strategic", "战略投资")):
        return "战略融资"
    return "融资"


def extract_capital_events(
    pages: Sequence[ParsedPage], aliases: Sequence[str], *, capital_market: bool = False
) -> list[dict[str, Any]]:
    keywords = CAPITAL_MARKET_KEYWORDS if capital_market else FINANCING_KEYWORDS
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for page in pages:
        sentences = sorted(
            (
                (_keyword_score(sentence, keywords, aliases), sentence)
                for sentence in sentences_for_page(page)
            ),
            key=lambda item: (-item[0], len(item[1])),
        )
        for score, sentence in sentences[:4]:
            if score < 4:
                continue
            key = re.sub(r"\W+", "", sentence).casefold()
            if key in seen:
                continue
            title = page.title if 8 <= len(page.title) <= 220 else sentence[:120]
            events.append(
                {
                    "date": page.published_at,
                    "type": _event_type(sentence, capital_market),
                    "title": title,
                    "summary": sentence,
                    "amount": _extract_amount(sentence),
                    "round": _extract_round(sentence),
                    "investors": [],
                    "sourceUrl": page.url,
                }
            )
            seen.add(key)
            if len(events) >= 12:
                return events
    return events


def source_record(page: ParsedPage, name: str, section: str) -> dict[str, str]:
    return {
        "name": name,
        "url": page.url,
        "level": "官方披露",
        "section": section,
        "title": page.title,
        "publishedAt": page.published_at,
    }


def _sentence_for_alias(page: ParsedPage, aliases: Sequence[str], fallback: str) -> str:
    for sentence in sentences_for_page(page):
        lowered = sentence.casefold()
        if any(alias.casefold() in lowered for alias in aliases if alias):
            return sentence
    return fallback


def _recent(date_value: str, now: datetime | None = None, days: int = 400) -> bool:
    if not date_value:
        return False
    try:
        parsed = datetime.fromisoformat(date_value).replace(tzinfo=UTC)
    except ValueError:
        return False
    current = now or datetime.now(UTC)
    return 0 <= (current - parsed).days <= days


def infer_investment_name(title: str) -> str:
    patterns = (
        r"(?:invests? in|backs?|leads? .*? in)\s+([A-Z][A-Za-z0-9&.\- ]{1,70})",
        r"(?:领投|投资|加码|参投)\s*([^，。；:：]{2,40})",
    )
    for pattern in patterns:
        match = re.search(pattern, title, re.IGNORECASE)
        if match:
            return clean_text(match.group(1), 100).strip(" -—:：,，。")
    return ""


def extract_institution_portfolio(
    pages: Sequence[ParsedPage], companies: Sequence[CatalogCompany], now: datetime | None = None
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    portfolio: list[dict[str, Any]] = []
    recent: list[dict[str, Any]] = []
    seen: set[str] = set()

    for page in pages:
        page_text = page.text.casefold()
        relevant_page = any(section in page.sections for section in ("portfolio", "recentInvestments"))
        if not relevant_page and not any(keyword.casefold() in page_text for keyword in INVESTMENT_ACTION_KEYWORDS):
            continue
        matched_on_page = False
        for company in companies:
            aliases = [alias for alias in company.aliases if len(alias) >= 2]
            if not any(alias.casefold() in page_text for alias in aliases):
                continue
            matched_on_page = True
            key = company.slug
            record = {
                "name": company.name,
                "companySlug": company.slug,
                "date": page.published_at,
                "round": _extract_round(page.text),
                "summary": _sentence_for_alias(
                    page,
                    aliases,
                    f"{company.name}出现在该机构公开投资组合或投资动态中。",
                ),
                "sourceUrl": page.url,
            }
            if key not in seen:
                portfolio.append(record)
                seen.add(key)
            if _recent(page.published_at, now) and any(
                keyword.casefold() in page_text for keyword in INVESTMENT_ACTION_KEYWORDS
            ):
                recent.append(record)

        if _recent(page.published_at, now) and not matched_on_page:
            name = infer_investment_name(page.title)
            if name:
                recent.append(
                    {
                        "name": name,
                        "date": page.published_at,
                        "round": _extract_round(page.text),
                        "summary": select_summary(
                            [page], INVESTMENT_ACTION_KEYWORDS, (name,), page.description or page.title, limit=360
                        ),
                        "sourceUrl": page.url,
                    }
                )

    recent_unique: list[dict[str, Any]] = []
    recent_seen: set[str] = set()
    for record in sorted(recent, key=lambda item: item.get("date", ""), reverse=True):
        key = f"{record.get('name','').casefold()}|{record.get('date','')}"
        if key in recent_seen:
            continue
        recent_unique.append(record)
        recent_seen.add(key)
        if len(recent_unique) >= 16:
            break

    company_by_slug = {company.slug: company for company in companies}
    classic_candidates = sorted(
        portfolio,
        key=lambda item: (
            company_by_slug.get(item.get("companySlug", ""), CatalogCompany("", "", "", "", "", "", "", "", "", "", "")).status
            != "已上市",
            item.get("name", ""),
        ),
    )
    classic: list[dict[str, Any]] = []
    for record in classic_candidates[:6]:
        company = company_by_slug.get(record.get("companySlug", ""))
        if company:
            exit_note = (
                "已进入公开市场，可继续用上市后经营与市值表现检验投资逻辑。"
                if company.status == "已上市"
                else "仍处于非上市阶段，后续轮融资、产品规模化和退出路径是主要检验点。"
            )
            analysis = (
                f"{company.name}位于{company.sector}赛道，核心产品为{company.product}。"
                f"该案例可用于观察机构在{company.stage}阶段的技术判断、后续资本支持与产业兑现，{exit_note}"
            )
        else:
            analysis = f"该案例用于观察机构从首次投资、后续融资支持到退出或长期持有的完整路径。"
        classic.append(
            {
                "name": record.get("name", ""),
                "companySlug": record.get("companySlug", ""),
                "analysis": clean_text(analysis, 520),
                "sourceUrl": record.get("sourceUrl", ""),
            }
        )

    return portfolio[:30], recent_unique, classic


def accepted_section_count(profile: dict[str, Any], kind: str) -> int:
    if kind == "company":
        return sum(
            bool(profile.get(field))
            for field in ("background", "technology", "products", "team", "financing", "capitalMarkets")
        )
    return sum(
        bool(profile.get(field))
        for field in ("overview", "strategy", "team", "recentInvestments", "portfolio", "classicCases")
    )


def evidence_score(profile: dict[str, Any], kind: str) -> int:
    sections = accepted_section_count(profile, kind)
    source_count = len(profile.get("sources", []))
    team_count = len(profile.get("team", []))
    event_count = len(profile.get("financing", [])) + len(profile.get("capitalMarkets", []))
    if kind == "institution":
        event_count = len(profile.get("recentInvestments", [])) + len(profile.get("portfolio", []))
    return min(100, sections * 12 + min(source_count, 10) * 4 + min(team_count, 5) * 3 + min(event_count, 8) * 2)
