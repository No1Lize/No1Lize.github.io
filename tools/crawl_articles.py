"""Build the public intelligence snapshot from free, first-party sources.

The crawler intentionally uses only Python's standard library.  GitHub Actions
can therefore run it on a schedule without a database, API server, paid plan or
package-install step.

Output:
    public/data/articles.json

Sources:
    * official company newsrooms
    * SEC EDGAR submissions for every US-listed company in the public catalog
    * SEC Company Facts for reported financial metrics
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"
LEGACY_PATH = ROOT / "data" / "public" / "dashboard.json"
MAX_ARTICLES = 600
MAX_NEWS_PER_SOURCE = 10
MAX_FILINGS_PER_COMPANY = 6
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
}
DEFAULT_USER_AGENT = (
    "LizeRoadOne/2.0 contact=No1Lize@users.noreply.github.com "
    "(+https://github.com/No1Lize/No1Lize.github.io)"
)


@dataclass(frozen=True)
class NewsSource:
    id: str
    name: str
    index_url: str
    company: str
    company_slug: str
    region: str
    sector: str
    path_prefixes: tuple[str, ...]


NEWS_SOURCES = (
    NewsSource(
        "openai",
        "OpenAI",
        "https://openai.com/news/",
        "OpenAI",
        "openai",
        "美国",
        "AI / AGI",
        ("/index/", "/news/"),
    ),
    NewsSource(
        "anthropic",
        "Anthropic",
        "https://www.anthropic.com/news",
        "Anthropic",
        "anthropic",
        "美国",
        "AI / AGI",
        ("/news/",),
    ),
    NewsSource(
        "figure",
        "Figure AI",
        "https://www.figure.ai/news",
        "Figure AI",
        "figure-ai",
        "美国",
        "机器人",
        ("/news/",),
    ),
    NewsSource(
        "xai",
        "xAI",
        "https://x.ai/news",
        "xAI",
        "xai",
        "美国",
        "AI / AGI",
        ("/news/",),
    ),
    NewsSource(
        "pony-ai",
        "Pony.ai Investor Relations",
        "https://ir.pony.ai/news-events/news-releases",
        "小马智行",
        "pony-ai",
        "中国",
        "机器人",
        ("/news-releases/news-release-details/",),
    ),
    NewsSource(
        "weride",
        "WeRide Investor Relations",
        "https://ir.weride.ai/news-events/news-releases/",
        "文远知行",
        "weride",
        "中国",
        "机器人",
        ("/news-releases/news-release-details/",),
    ),
    NewsSource(
        "rocket-lab",
        "Rocket Lab",
        "https://www.rocketlabusa.com/updates/",
        "Rocket Lab",
        "rocket-lab",
        "美国",
        "商业航天",
        ("/updates/",),
    ),
    NewsSource(
        "ionq",
        "IonQ",
        "https://ionq.com/news",
        "IonQ",
        "ionq",
        "美国",
        "量子计算",
        ("/news/",),
    ),
    NewsSource(
        "catl",
        "CATL",
        "https://www.catl.com/en/news/",
        "宁德时代",
        "catl",
        "中国",
        "新能源",
        ("/en/news/",),
    ),
)


# Tickers are resolved against SEC's own company_tickers.json on every run, so a
# CIK is never guessed or silently kept after an issuer changes its filing key.
SEC_TRACKED = {
    "PONY": ("小马智行", "pony-ai", "机器人"),
    "WRD": ("文远知行", "weride", "机器人"),
    "RGTI": ("Rigetti Computing", "rigetti", "量子计算"),
    "IONQ": ("IonQ", "ionq", "量子计算"),
    "RKLB": ("Rocket Lab", "rocket-lab", "商业航天"),
    "TEM": ("Tempus AI", "tempus-ai", "生物科技"),
    "RXRX": ("Recursion Pharmaceuticals", "recursion", "生物科技"),
    "MBLY": ("Mobileye", "mobileye", "半导体"),
    "AUR": ("Aurora Innovation", "aurora", "机器人"),
    "JOBY": ("Joby Aviation", "joby", "商业航天"),
}

SUPPORTED_FORMS = {
    "10-K",
    "10-Q",
    "20-F",
    "6-K",
    "8-K",
    "S-1",
    "F-1",
    "424B4",
}

FINANCIAL_CONCEPTS = (
    (
        "revenue",
        "营业收入",
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ),
    ),
    ("netIncome", "净利润", ("NetIncomeLoss", "ProfitLoss")),
    (
        "researchAndDevelopment",
        "研发投入",
        ("ResearchAndDevelopmentExpense",),
    ),
    (
        "operatingCashFlow",
        "经营现金流",
        ("NetCashProvidedByUsedInOperatingActivities",),
    ),
)


class ArticleHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.links: list[str] = []
        self.time_values: list[str] = []
        self._capture: str | None = None
        self._buffers: dict[str, list[str]] = {"h1": [], "title": []}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "meta":
            key = (values.get("property") or values.get("name")).lower()
            content = values.get("content", "").strip()
            if key and content:
                self.meta[key] = content
        elif tag == "a" and values.get("href"):
            self.links.append(values["href"])
        elif tag == "time" and values.get("datetime"):
            self.time_values.append(values["datetime"])
        elif tag in self._buffers:
            self._capture = tag

    def handle_endtag(self, tag: str) -> None:
        if tag == self._capture:
            self._capture = None

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._buffers[self._capture].append(data)

    def text(self, tag: str) -> str:
        return clean_text(" ".join(self._buffers.get(tag, [])))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def normalize_url(url: str) -> str:
    parts = urlsplit(url)
    query = urlencode(
        sorted(
            (key, value)
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in TRACKING_PARAMETERS
        )
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, query, "")
    )


def article_id(prefix: str, url: str) -> str:
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


def fetch_text(url: str, user_agent: str, timeout: int = 30) -> str:
    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/json,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode(
            response.headers.get_content_charset() or "utf-8", errors="replace"
        )


def normalize_date(value: str | None) -> str | None:
    if not value:
        return None
    iso_match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    if iso_match:
        return iso_match.group(0)
    named = re.search(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2}),?\s+(\d{4})",
        value,
        flags=re.IGNORECASE,
    )
    if named:
        try:
            return datetime.strptime(
                " ".join(named.groups()), "%B %d %Y"
            ).date().isoformat()
        except ValueError:
            return None
    return None


def infer_event_type(title: str, summary: str = "") -> tuple[str, int]:
    text = f"{title} {summary}".casefold()
    rules = (
        (("raises", "funding", "financing", "series ", "融资", "领投"), "融资", 91),
        (("acquire", "acquisition", "merger", "并购", "收购"), "并购", 89),
        (("ipo", "nasdaq", "nyse", "hkex", "上市", "招股"), "IPO", 90),
        (
            ("financial results", "earnings", "annual report", "财报", "业绩"),
            "财报",
            82,
        ),
        (
            ("partnership", "agreement", "deploy", "customer", "合作", "签署", "落地"),
            "商业进展",
            84,
        ),
        (
            ("launch", "introducing", "release", "available", "发布", "推出"),
            "产品发布",
            81,
        ),
        (
            ("research", "breakthrough", "model", "benchmark", "技术", "研究"),
            "技术突破",
            85,
        ),
        (("policy", "regulation", "government", "监管", "政策"), "政策", 83),
        (("investment", "infrastructure", "fund", "投资", "基金"), "产业投资", 84),
    )
    for keywords, event_type, importance in rules:
        if any(keyword in text for keyword in keywords):
            return event_type, importance
    return "公司动态", 76


def _published_value(parser: ArticleHTMLParser, body: str) -> str | None:
    value = (
        parser.meta.get("article:published_time")
        or parser.meta.get("date")
        or parser.meta.get("datepublished")
        or parser.meta.get("publishdate")
        or (parser.time_values[0] if parser.time_values else None)
    )
    if value:
        return value
    for pattern in (
        r'"datePublished"\s*:\s*"([^"]+)"',
        r'"dateCreated"\s*:\s*"([^"]+)"',
        r'"publishDate"\s*:\s*"([^"]+)"',
    ):
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    # Several investor-relations templates expose the release date as plain
    # English text but not as metadata.
    named = re.search(
        r"(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+\d{1,2},?\s+\d{4}",
        body,
        flags=re.IGNORECASE,
    )
    return named.group(0) if named else None


def parse_news_article(
    source: NewsSource, url: str, body: str
) -> dict[str, Any] | None:
    parser = ArticleHTMLParser()
    parser.feed(body)
    title = clean_text(
        parser.text("h1")
        or parser.meta.get("og:title", "")
        or parser.text("title")
    )
    if not title or title.casefold() in {
        source.name.casefold(),
        "news",
        "newsroom",
        "updates",
    }:
        return None
    published_at = normalize_date(_published_value(parser, body))
    if not published_at:
        return None
    summary = clean_text(
        parser.meta.get("description", "")
        or parser.meta.get("og:description", "")
        or parser.meta.get("twitter:description", "")
    )
    if not summary:
        summary = f"{source.name} 发布“{title}”；完整内容与数据见公司原文。"
    summary = summary[:500].rstrip()
    event_type, importance = infer_event_type(title, summary)
    canonical_url = normalize_url(
        parser.meta.get("og:url", "") or url
    )
    return {
        "id": article_id(source.id, canonical_url),
        "title": title[:220],
        "summary": summary,
        "type": event_type,
        "region": source.region,
        "sector": source.sector,
        "company": source.company,
        "companySlug": source.company_slug,
        "publishedAt": published_at,
        "importance": importance,
        "source": {
            "name": source.name,
            "url": canonical_url,
            "level": "官方披露",
        },
    }


def discover_news_urls(source: NewsSource, body: str) -> list[str]:
    parser = ArticleHTMLParser()
    parser.feed(body)
    index_url = normalize_url(source.index_url)
    index_parts = urlsplit(index_url)
    discovered: list[str] = []
    for href in parser.links:
        absolute = normalize_url(urljoin(source.index_url, href))
        parts = urlsplit(absolute)
        if parts.netloc != index_parts.netloc:
            continue
        if absolute == index_url:
            continue
        if not any(parts.path.startswith(prefix) for prefix in source.path_prefixes):
            continue
        if absolute not in discovered:
            discovered.append(absolute)
    return discovered[:MAX_NEWS_PER_SOURCE]


def crawl_news_source(
    source: NewsSource, user_agent: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    index_body = fetch_text(source.index_url, user_agent)
    urls = discover_news_urls(source, index_body)
    articles: list[dict[str, Any]] = []
    failures = 0
    for url in urls:
        try:
            parsed = parse_news_article(source, url, fetch_text(url, user_agent))
            if parsed:
                articles.append(parsed)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            failures += 1
    if not articles:
        raise RuntimeError(
            f"no dated articles parsed from {len(urls)} discovered links"
        )
    return articles, {
        "id": source.id,
        "name": source.name,
        "status": "ok",
        "scanned": len(urls),
        "accepted": len(articles),
        "failed": failures,
    }


def crawl_company_news(
    user_agent: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    errors: list[str] = []
    for source in NEWS_SOURCES:
        try:
            incoming, status = crawl_news_source(source, user_agent)
            articles.extend(incoming)
            statuses.append(status)
        except Exception as exc:
            message = f"{source.id}: {type(exc).__name__}: {exc}"
            errors.append(message)
            statuses.append(
                {
                    "id": source.id,
                    "name": source.name,
                    "status": "error",
                    "scanned": 0,
                    "accepted": 0,
                }
            )
            print(f"News source warning: {message}", file=sys.stderr)
    if not articles:
        raise RuntimeError("all company news sources returned no articles")
    return articles, statuses, errors


def sec_article(
    *,
    cik: str,
    company: str,
    company_slug: str,
    sector: str,
    form: str,
    filing_date: str,
    accession_number: str,
    primary_document: str,
) -> dict[str, Any]:
    accession_path = accession_number.replace("-", "")
    url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
        f"{accession_path}/{primary_document}"
    )
    importance = {
        "S-1": 94,
        "F-1": 94,
        "424B4": 92,
        "10-K": 87,
        "20-F": 87,
        "10-Q": 82,
        "6-K": 79,
        "8-K": 80,
    }.get(form, 74)
    event_type = (
        "IPO"
        if form in {"S-1", "F-1", "424B4"}
        else "财报"
        if form in {"10-K", "10-Q", "20-F"}
        else "监管文件"
    )
    label = {
        "10-K": "年度报告",
        "20-F": "年度报告",
        "10-Q": "季度报告",
        "6-K": "境外发行人报告",
        "8-K": "重大事项报告",
        "S-1": "上市注册文件",
        "F-1": "境外发行人上市注册文件",
        "424B4": "最终招股文件",
    }.get(form, "监管文件")
    return {
        "id": article_id("sec", url),
        "title": f"{company} 提交 {form}（{label}）",
        "summary": (
            f"SEC EDGAR 于 {filing_date} 收录 {company} 的 {form} 文件。"
            "原始文件包含本次披露的完整正文、附件和财务口径。"
        ),
        "type": event_type,
        "region": "美国",
        "sector": sector,
        "company": company,
        "companySlug": company_slug,
        "publishedAt": filing_date,
        "importance": importance,
        "source": {
            "name": "SEC EDGAR",
            "url": normalize_url(url),
            "level": "监管文件",
        },
    }


def _resolve_sec_companies(
    user_agent: str,
) -> dict[str, tuple[str, str, str, str]]:
    body = fetch_text("https://www.sec.gov/files/company_tickers.json", user_agent)
    ticker_rows = json.loads(body)
    by_ticker = {
        row["ticker"].upper(): str(row["cik_str"]).zfill(10)
        for row in ticker_rows.values()
    }
    resolved: dict[str, tuple[str, str, str, str]] = {}
    for ticker, (company, slug, sector) in SEC_TRACKED.items():
        cik = by_ticker.get(ticker)
        if cik:
            resolved[ticker] = (cik, company, slug, sector)
    return resolved


def _filing_arrays(recent: dict[str, Any]) -> Iterable[dict[str, str]]:
    forms = recent.get("form", [])
    for index, form in enumerate(forms):
        if form not in SUPPORTED_FORMS:
            continue
        try:
            yield {
                "form": form,
                "filingDate": recent["filingDate"][index],
                "accessionNumber": recent["accessionNumber"][index],
                "primaryDocument": recent["primaryDocument"][index],
            }
        except (IndexError, KeyError):
            continue


def _latest_metric(
    company_facts: dict[str, Any],
    metric_id: str,
    label: str,
    concepts: tuple[str, ...],
) -> dict[str, Any] | None:
    namespace = company_facts.get("facts", {}).get("us-gaap", {})
    candidates: list[dict[str, Any]] = []
    for concept in concepts:
        units = namespace.get(concept, {}).get("units", {})
        for unit in ("USD", "USD/shares"):
            for fact in units.get(unit, []):
                if fact.get("form") not in {"10-K", "10-Q", "20-F", "6-K"}:
                    continue
                if not all(key in fact for key in ("val", "filed", "end")):
                    continue
                candidates.append(
                    {
                        "id": metric_id,
                        "label": label,
                        "value": fact["val"],
                        "unit": unit,
                        "periodEnd": fact["end"],
                        "filedAt": fact["filed"],
                        "form": fact.get("form"),
                        "fiscalYear": fact.get("fy"),
                        "fiscalPeriod": fact.get("fp"),
                        "accessionNumber": fact.get("accn"),
                        "concept": concept,
                    }
                )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item.get("filedAt", ""),
            item.get("periodEnd", ""),
            str(item.get("accessionNumber", "")),
        ),
    )


def _company_financials(
    *,
    cik: str,
    ticker: str,
    company: str,
    company_slug: str,
    body: str,
) -> dict[str, Any]:
    company_facts = json.loads(body)
    metrics = [
        metric
        for metric_id, label, concepts in FINANCIAL_CONCEPTS
        if (
            metric := _latest_metric(
                company_facts, metric_id, label, concepts
            )
        )
    ]
    return {
        "company": company,
        "companySlug": company_slug,
        "ticker": ticker,
        "cik": cik,
        "entityName": company_facts.get("entityName") or company,
        "metrics": metrics,
        "source": {
            "name": "SEC Company Facts",
            "url": f"https://www.sec.gov/edgar/browse/?CIK={int(cik)}",
            "level": "监管文件",
        },
    }


def crawl_sec(
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    company_facts: dict[str, Any] = {}
    resolved = _resolve_sec_companies(user_agent)
    failures = 0
    for ticker, (cik, company, company_slug, sector) in resolved.items():
        try:
            submissions_url = (
                f"https://data.sec.gov/submissions/CIK{cik}.json"
            )
            recent = json.loads(
                fetch_text(submissions_url, user_agent)
            ).get("filings", {}).get("recent", {})
            filings = list(_filing_arrays(recent))[:MAX_FILINGS_PER_COMPANY]
            for filing in filings:
                articles.append(
                    sec_article(
                        cik=cik,
                        company=company,
                        company_slug=company_slug,
                        sector=sector,
                        form=filing["form"],
                        filing_date=filing["filingDate"],
                        accession_number=filing["accessionNumber"],
                        primary_document=filing["primaryDocument"],
                    )
                )
            facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
            company_facts[company_slug] = _company_financials(
                cik=cik,
                ticker=ticker,
                company=company,
                company_slug=company_slug,
                body=fetch_text(facts_url, user_agent),
            )
        except Exception as exc:
            failures += 1
            print(
                f"SEC warning: {ticker} ({type(exc).__name__}: {exc})",
                file=sys.stderr,
            )
    if not articles:
        raise RuntimeError("SEC returned no supported filings")
    return articles, company_facts, {
        "id": "sec",
        "name": "SEC EDGAR",
        "status": "ok" if failures == 0 else "partial",
        "scanned": len(resolved),
        "accepted": len(articles),
        "failed": failures,
    }


def load_existing_payload(
    output_path: Path = OUTPUT_PATH, legacy_path: Path = LEGACY_PATH
) -> dict[str, Any]:
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    if legacy_path.exists():
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        return {
            "schemaVersion": 2,
            "generatedAt": legacy.get("updated_at"),
            "articleCount": len(legacy.get("events", [])),
            "articles": legacy.get("events", []),
            "companyFacts": {},
            "sourceStatus": [],
        }
    return {
        "schemaVersion": 2,
        "generatedAt": None,
        "articleCount": 0,
        "articles": [],
        "companyFacts": {},
        "sourceStatus": [],
    }


def _title_fingerprint(article: dict[str, Any]) -> str:
    title = re.sub(r"[^\w\u4e00-\u9fff]+", "", article.get("title", "").casefold())
    return "|".join(
        (
            article.get("companySlug") or article.get("company", ""),
            article.get("publishedAt", ""),
            title,
        )
    )


def merge_articles(
    existing: list[dict[str, Any]], incoming: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for article in existing:
        source_url = article.get("source", {}).get("url")
        if source_url:
            merged[normalize_url(source_url)] = article
    for article in incoming:
        source_url = article["source"]["url"]
        key = normalize_url(source_url)
        if key in merged:
            previous = merged[key]
            curated = bool(previous.get("curated"))
            merged[key] = {
                **previous,
                **article,
                "id": previous.get("id", article["id"]),
                "title": (
                    previous.get("title") if curated else article.get("title")
                )
                or previous.get("title")
                or article["title"],
                "summary": (
                    previous.get("summary")
                    if curated
                    else article.get("summary")
                )
                or previous.get("summary")
                or article["summary"],
                "importance": max(
                    int(previous.get("importance", 0)),
                    int(article.get("importance", 0)),
                ),
            }
        else:
            merged[key] = article

    deduplicated: dict[str, dict[str, Any]] = {}
    for article in sorted(
        merged.values(),
        key=lambda item: (
            item.get("publishedAt", ""),
            int(item.get("importance", 0)),
            item.get("id", ""),
        ),
        reverse=True,
    ):
        fingerprint = _title_fingerprint(article)
        if fingerprint not in deduplicated:
            deduplicated[fingerprint] = article
    return list(deduplicated.values())[:MAX_ARTICLES]


def write_if_changed(
    articles: list[dict[str, Any]],
    previous_payload: dict[str, Any],
    output_path: Path = OUTPUT_PATH,
    *,
    company_facts: dict[str, Any] | None = None,
    source_status: list[dict[str, Any]] | None = None,
) -> bool:
    next_company_facts = (
        company_facts
        if company_facts is not None
        else previous_payload.get("companyFacts", {})
    )
    next_source_status = (
        source_status
        if source_status is not None
        else previous_payload.get("sourceStatus", [])
    )
    unchanged = (
        articles == previous_payload.get("articles", [])
        and next_company_facts == previous_payload.get("companyFacts", {})
        and next_source_status == previous_payload.get("sourceStatus", [])
        and output_path.exists()
        and previous_payload.get("schemaVersion") == 2
    )
    if unchanged:
        print(f"No snapshot changes ({len(articles)} articles).")
        return False
    payload = {
        "schemaVersion": 2,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "articleCount": len(articles),
        "articles": articles,
        "companyFacts": next_company_facts,
        "sourceStatus": next_source_status,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Updated {output_path.relative_to(ROOT)} "
        f"({len(articles)} articles, {len(next_company_facts)} financial profiles)."
    )
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=("all", "news", "sec"), default="all"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Only migrate and normalize the existing snapshot.",
    )
    args = parser.parse_args()

    payload = load_existing_payload()
    incoming: list[dict[str, Any]] = []
    company_facts = dict(payload.get("companyFacts", {}))
    source_status: list[dict[str, Any]] = []
    errors: list[str] = []
    selected = ("news", "sec") if args.source == "all" else (args.source,)
    user_agent = (
        os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    )

    if not args.offline:
        for source in selected:
            try:
                if source == "news":
                    news, statuses, news_errors = crawl_company_news(user_agent)
                    incoming.extend(news)
                    source_status.extend(statuses)
                    errors.extend(news_errors)
                else:
                    sec_articles, sec_facts, status = crawl_sec(user_agent)
                    incoming.extend(sec_articles)
                    company_facts.update(sec_facts)
                    source_status.append(status)
            except Exception as exc:
                errors.append(f"{source}: {type(exc).__name__}: {exc}")

    merged = merge_articles(payload.get("articles", []), incoming)
    write_if_changed(
        merged,
        payload,
        company_facts=company_facts,
        source_status=source_status or payload.get("sourceStatus", []),
    )
    print(
        json.dumps(
            {
                "sources": list(selected),
                "incoming": len(incoming),
                "total": len(merged),
                "financialProfiles": len(company_facts),
                "errors": errors,
            },
            ensure_ascii=False,
        )
    )
    if not args.offline and errors and not incoming:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
