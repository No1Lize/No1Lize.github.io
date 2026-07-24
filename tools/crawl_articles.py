"""Fetch public first-party sources and maintain public/data/articles.json.

The script intentionally uses only Python's standard library so GitHub Actions
does not need a package installation step or any paid service.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import sys
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"
LEGACY_PATH = ROOT / "data" / "public" / "dashboard.json"
MAX_ARTICLES = 500
OPENAI_NEWS_URL = "https://openai.com/news/"
OPENAI_SEED_URLS = (
    "https://openai.com/index/accelerating-the-next-phase-ai/",
    "https://openai.com/index/announcing-the-stargate-project/",
)
SEC_COMPANIES = {
    "0001824920": ("IonQ", "ionq", "量子计算"),
    "0001819994": ("Rocket Lab", "rocket-lab", "商业航天"),
    "0001838359": ("Rigetti Computing", "rigetti", "量子计算"),
}
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "ref",
}
DEFAULT_USER_AGENT = (
    "LizeRoadOne/1.0 (+https://github.com/No1Lize/No1Lize.github.io)"
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
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Encoding": "identity",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode(
            response.headers.get_content_charset() or "utf-8", errors="replace"
        )


def normalize_date(value: str | None) -> str:
    if not value:
        return datetime.now(UTC).date().isoformat()
    match = re.search(r"\d{4}-\d{2}-\d{2}", value)
    return match.group(0) if match else datetime.now(UTC).date().isoformat()


def infer_openai_type(title: str) -> tuple[str, int]:
    lowered = title.casefold()
    if any(word in lowered for word in ("funding", "financing", "raises", "investment")):
        return "融资", 88
    if any(word in lowered for word in ("infrastructure", "partnership", "stargate")):
        return "产业投资", 86
    if any(word in lowered for word in ("research", "model", "reasoning", "science")):
        return "技术突破", 84
    return "产品发布", 80


def parse_openai_article(url: str, body: str) -> dict[str, Any] | None:
    parser = ArticleHTMLParser()
    parser.feed(body)
    title = clean_text(
        parser.text("h1")
        or parser.meta.get("og:title", "")
        or parser.text("title")
    )
    if not title:
        return None
    summary = clean_text(
        parser.meta.get("description", "")
        or parser.meta.get("og:description", "")
        or "OpenAI 官方页面更新。"
    )
    raw_date = (
        parser.meta.get("article:published_time")
        or parser.meta.get("date")
        or parser.meta.get("datepublished")
        or (parser.time_values[0] if parser.time_values else None)
    )
    if not raw_date:
        date_match = re.search(
            r'"datePublished"\s*:\s*"([^"]+)"', body, flags=re.IGNORECASE
        )
        raw_date = date_match.group(1) if date_match else None
    event_type, importance = infer_openai_type(title)
    canonical_url = normalize_url(url)
    return {
        "id": article_id("openai", canonical_url),
        "title": title,
        "summary": summary,
        "type": event_type,
        "region": "美国",
        "sector": "AI / AGI",
        "company": "OpenAI",
        "companySlug": "openai",
        "publishedAt": normalize_date(raw_date),
        "importance": importance,
        "source": {
            "name": "OpenAI",
            "url": canonical_url,
            "level": "官方披露",
        },
    }


def discover_openai_urls(body: str) -> list[str]:
    parser = ArticleHTMLParser()
    parser.feed(body)
    discovered: list[str] = []
    for href in parser.links:
        absolute = normalize_url(urljoin(OPENAI_NEWS_URL, href))
        parts = urlsplit(absolute)
        if parts.netloc not in {"openai.com", "www.openai.com"}:
            continue
        if not (
            parts.path.startswith("/index/")
            or parts.path.startswith("/news/")
        ):
            continue
        if parts.path.rstrip("/") in {"/index", "/news"}:
            continue
        if absolute not in discovered:
            discovered.append(absolute)
    return discovered[:12]


def crawl_openai(user_agent: str) -> list[dict[str, Any]]:
    urls = list(OPENAI_SEED_URLS)
    try:
        index_body = fetch_text(OPENAI_NEWS_URL, user_agent)
        urls.extend(
            url for url in discover_openai_urls(index_body) if url not in urls
        )
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        print(f"OpenAI index warning: {type(exc).__name__}", file=sys.stderr)

    articles: list[dict[str, Any]] = []
    failures = 0
    for url in urls:
        try:
            parsed = parse_openai_article(url, fetch_text(url, user_agent))
            if parsed:
                articles.append(parsed)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            failures += 1
            print(
                f"OpenAI page warning: {url} ({type(exc).__name__})",
                file=sys.stderr,
            )
    if not articles:
        raise RuntimeError(f"OpenAI returned no articles ({failures} failed requests)")
    return articles


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
        "S-1": 92,
        "424B4": 90,
        "10-K": 84,
        "8-K": 78,
        "10-Q": 74,
    }.get(form, 70)
    return {
        "id": article_id("sec", url),
        "title": f"{company} 提交 {form}",
        "summary": (
            f"SEC EDGAR 显示 {company} 于 {filing_date} 提交 {form}；"
            "点击原始来源可核对完整监管文件。"
        ),
        "type": "监管文件",
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


def crawl_sec(user_agent: str) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for cik, (company, company_slug, sector) in SEC_COMPANIES.items():
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        body = fetch_text(url, user_agent)
        recent = json.loads(body).get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        for index, form in enumerate(forms[:20]):
            if form not in {"10-K", "10-Q", "8-K", "S-1", "424B4"}:
                continue
            articles.append(
                sec_article(
                    cik=cik,
                    company=company,
                    company_slug=company_slug,
                    sector=sector,
                    form=form,
                    filing_date=recent["filingDate"][index],
                    accession_number=recent["accessionNumber"][index],
                    primary_document=recent["primaryDocument"][index],
                )
            )
    if not articles:
        raise RuntimeError("SEC returned no supported filings")
    return articles


def load_existing_payload(
    output_path: Path = OUTPUT_PATH, legacy_path: Path = LEGACY_PATH
) -> dict[str, Any]:
    if output_path.exists():
        return json.loads(output_path.read_text(encoding="utf-8"))
    if legacy_path.exists():
        legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
        return {
            "schemaVersion": 1,
            "generatedAt": legacy.get("updated_at"),
            "articleCount": len(legacy.get("events", [])),
            "articles": legacy.get("events", []),
        }
    return {
        "schemaVersion": 1,
        "generatedAt": None,
        "articleCount": 0,
        "articles": [],
    }


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
            merged[key] = {
                **article,
                "id": previous.get("id", article["id"]),
                "title": previous.get("title") or article["title"],
                "summary": previous.get("summary") or article["summary"],
                "importance": max(
                    int(previous.get("importance", 0)),
                    int(article.get("importance", 0)),
                ),
            }
        else:
            merged[key] = article
    return sorted(
        merged.values(),
        key=lambda item: (
            item.get("publishedAt", ""),
            int(item.get("importance", 0)),
            item.get("id", ""),
        ),
        reverse=True,
    )[:MAX_ARTICLES]


def write_if_changed(
    articles: list[dict[str, Any]],
    previous_payload: dict[str, Any],
    output_path: Path = OUTPUT_PATH,
) -> bool:
    previous_articles = previous_payload.get("articles", [])
    if articles == previous_articles and output_path.exists():
        print(f"No article changes ({len(articles)} records).")
        return False
    payload = {
        "schemaVersion": 1,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "articleCount": len(articles),
        "articles": articles,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Updated {output_path.relative_to(ROOT)} ({len(articles)} records).")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source", choices=("all", "openai", "sec"), default="all"
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Only migrate/normalize existing data without network requests.",
    )
    args = parser.parse_args()

    payload = load_existing_payload()
    incoming: list[dict[str, Any]] = []
    errors: list[str] = []
    selected = (
        ("openai", "sec") if args.source == "all" else (args.source,)
    )
    user_agent = (
        os.environ.get("SEC_USER_AGENT", "").strip() or DEFAULT_USER_AGENT
    )

    if not args.offline:
        for source in selected:
            try:
                incoming.extend(
                    crawl_openai(user_agent)
                    if source == "openai"
                    else crawl_sec(user_agent)
                )
            except Exception as exc:
                errors.append(f"{source}: {type(exc).__name__}: {exc}")

    merged = merge_articles(payload.get("articles", []), incoming)
    write_if_changed(merged, payload)
    print(
        json.dumps(
            {
                "sources": list(selected),
                "incoming": len(incoming),
                "total": len(merged),
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
