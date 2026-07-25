#!/usr/bin/env python3
"""Crawl traceable WeChat public-account articles from public search indexes.

The crawler uses only public index results and public ``mp.weixin.qq.com`` pages.
It stores short metadata summaries and entity links, never a full article copy.
If an account cannot be refreshed, its previous snapshot is retained.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote_plus, urlencode, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "wechat_sources.json"
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
OUTPUT_PATH = ROOT / "public" / "data" / "articles.json"
DEFAULT_USER_AGENT = (
    "LizeRoadOne/3.0 contact=No1Lize@users.noreply.github.com "
    "(+https://github.com/No1Lize/No1Lize.github.io)"
)
WECHAT_PREFIX = "wechat-"
MAX_TOTAL_ARTICLES = 600
VALID_REGIONS = {"中国", "美国", "全球"}
VALID_SOURCE_LEVELS = {
    "官方披露",
    "原始材料",
    "监管文件",
    "媒体报道",
    "数据库记录",
    "待交叉验证",
}
TRACKING_PARAMETERS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "source",
    "scene",
    "from",
    "isappinstalled",
}
EVENT_RULES: tuple[tuple[tuple[str, ...], str, int], ...] = (
    (("融资", "领投", "投资方", "完成数亿元", "完成数千万"), "融资", 89),
    (("收购", "并购", "合并"), "并购", 88),
    (("IPO", "招股书", "上市申请", "通过聆讯", "科创板"), "IPO", 89),
    (("财报", "业绩", "营收", "净利润", "季度报告", "年度报告"), "财报", 83),
    (("政策", "监管", "管理办法", "指导意见", "国家标准"), "政策", 85),
    (("发布", "推出", "上线", "首发", "新品", "量产"), "产品发布", 82),
    (("突破", "刷新纪录", "研究成果", "论文", "新方法"), "技术突破", 84),
    (("合作", "签约", "订单", "中标", "落地", "建厂", "投产"), "商业进展", 81),
)


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(value or "")).strip()


def strip_html(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value or "")
    return clean_text(re.sub(r"(?s)<[^>]+>", " ", value))


def normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", clean_text(value).casefold())


def normalize_url(value: str) -> str:
    parts = urlsplit(clean_text(value))
    query = urlencode(
        sorted(
            (key, item)
            for key, item in parse_qsl(parts.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        )
    )
    return urlunsplit(
        (parts.scheme.casefold(), parts.netloc.casefold(), parts.path or "/", query, "")
    )


def article_id(source_id: str, url: str) -> str:
    digest = hashlib.sha256(normalize_url(url).encode("utf-8")).hexdigest()[:16]
    return f"{source_id}-{digest}"


def normalize_date(value: str | int | float | None) -> str | None:
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)) or str(value).isdigit():
            number = float(value)
            if number > 10_000_000_000:
                number /= 1000
            parsed = datetime.fromtimestamp(number, tz=UTC).date()
            if parsed <= datetime.now(UTC).date() + timedelta(days=2):
                return parsed.isoformat()
    except (OSError, OverflowError, ValueError):
        pass
    text = clean_text(str(value))
    match = re.search(r"\d{4}-\d{2}-\d{2}", text)
    if match:
        try:
            parsed = date.fromisoformat(match.group(0))
            if parsed <= datetime.now(UTC).date() + timedelta(days=2):
                return parsed.isoformat()
        except ValueError:
            pass
    localized = re.search(
        r"(?<!\d)(\d{4})\s*(?:年|[/.])\s*(\d{1,2})\s*(?:月|[/.])\s*(\d{1,2})\s*日?",
        text,
    )
    if localized:
        try:
            return date(*(int(part) for part in localized.groups())).isoformat()
        except ValueError:
            pass
    try:
        parsed_dt = parsedate_to_datetime(text)
        if parsed_dt:
            return parsed_dt.date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass
    return None


def fetch_text(url: str, user_agent: str, timeout: int = 18, attempts: int = 2) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml,text/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read().decode(
                    response.headers.get_content_charset() or "utf-8",
                    errors="replace",
                )
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(0.8 * (attempt + 1))
    assert last_error is not None
    raise last_error


class WeChatArticleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.title_parts: list[str] = []
        self.content_parts: list[str] = []
        self._in_title = False
        self._content_depth = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        values = {key.casefold(): value or "" for key, value in attrs}
        tag = tag.casefold()
        if tag == "meta":
            key = (
                values.get("property")
                or values.get("name")
                or values.get("itemprop")
                or ""
            ).casefold()
            content = clean_text(values.get("content", ""))
            if key and content:
                self.meta[key] = content
        if tag == "title":
            self._in_title = True
        if values.get("id") == "js_content":
            self._content_depth = 1
        elif self._content_depth:
            self._content_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "title":
            self._in_title = False
        if self._content_depth:
            self._content_depth -= 1

    def handle_data(self, data: str) -> None:
        value = clean_text(data)
        if not value:
            return
        if self._in_title:
            self.title_parts.append(value)
        if self._content_depth:
            self.content_parts.append(value)


def _decode_js_string(value: str) -> str:
    try:
        return clean_text(json.loads(f'"{value}"'))
    except (json.JSONDecodeError, ValueError):
        return clean_text(value.replace(r"\x26", "&").replace(r"\/", "/"))


def _script_value(body: str, names: Sequence[str]) -> str:
    for name in names:
        match = re.search(
            rf"(?:var\s+)?{re.escape(name)}\s*=\s*['\"]((?:\\.|[^'\"])*)['\"]",
            body,
            flags=re.IGNORECASE,
        )
        if match:
            return _decode_js_string(match.group(1))
    return ""


def account_matches(configured: dict[str, Any], observed: str) -> bool:
    observed_key = normalized_key(observed)
    if not observed_key:
        return False
    expected = [configured.get("name", ""), configured.get("accountId", "")]
    return any(
        key and (key == observed_key or key in observed_key or observed_key in key)
        for key in (normalized_key(str(value)) for value in expected)
    )


def _contains_entity(text: str, entity: str) -> bool:
    entity = clean_text(entity)
    if not entity:
        return False
    if re.fullmatch(r"[A-Za-z0-9 .&+_-]+", entity):
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){re.escape(entity)}(?![A-Za-z0-9])",
                text,
                flags=re.IGNORECASE,
            )
        )
    return entity in text


def unique(values: Iterable[str], limit: int = 100) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = clean_text(value)
        key = normalized_key(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def tracking_by_sector() -> dict[str, dict[str, list[str]]]:
    if not TRACKING_PATH.exists():
        return {}
    try:
        payload = json.loads(TRACKING_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, list[str]]] = {}
    for raw in payload.get("tracks", []):
        if not isinstance(raw, dict) or raw.get("enabled", True) is False:
            continue
        name = clean_text(str(raw.get("name") or ""))
        if not name:
            continue
        result[name.casefold()] = {
            "keywords": unique(str(value) for value in raw.get("keywords", [])),
            "companies": unique(str(value) for value in raw.get("sampleCompanies", [])),
            "people": unique(str(value).split("@")[0] for value in raw.get("people", [])),
        }
    return result


def account_entities(
    account: dict[str, Any], sector: str, tracking: dict[str, dict[str, list[str]]]
) -> tuple[list[str], list[str], list[str]]:
    linked = tracking.get(sector.casefold(), {})
    keywords = unique(
        [
            *account.get("sectorKeywords", {}).get(sector, []),
            *linked.get("keywords", []),
        ],
        50,
    )
    companies = unique([*account.get("companies", []), *linked.get("companies", [])], 60)
    people = unique([*account.get("people", []), *linked.get("people", [])], 60)
    return keywords, companies, people


def choose_sector(
    account: dict[str, Any], text: str, tracking: dict[str, dict[str, list[str]]]
) -> str:
    scores: Counter[str] = Counter()
    for sector in account.get("sectorKeywords", {}):
        keywords, _, _ = account_entities(account, sector, tracking)
        scores[sector] = sum(1 for keyword in keywords if _contains_entity(text, keyword))
    if scores:
        highest = max(scores.values())
        if highest > 0:
            winners = [sector for sector, score in scores.items() if score == highest]
            default = clean_text(str(account.get("defaultSector") or ""))
            return default if default in winners else sorted(winners)[0]
    return clean_text(str(account.get("defaultSector") or "AI / AGI"))


def infer_event_type(title: str, summary: str) -> tuple[str, int]:
    text = f"{title} {summary}".casefold()
    for terms, event_type, importance in EVENT_RULES:
        if any(term.casefold() in text for term in terms):
            return event_type, importance
    return "公司动态", 75


def short_summary(description: str, content: str, account_name: str, title: str) -> str:
    candidate = clean_text(description)
    if len(candidate) < 24 or candidate in {title, account_name}:
        candidate = clean_text(content)
    candidate = re.sub(
        r"^(?:点击蓝字关注|关注我们|来源[:：]|本文转载自)\s*", "", candidate
    )
    if len(candidate) > 260:
        sentence = re.split(r"(?<=[。！？!?])", candidate[:320])[0]
        candidate = sentence if len(sentence) >= 60 else candidate[:260]
    return candidate[:260].rstrip("，,；;：:") or f"{account_name} 发布“{title}”，完整内容见原文。"


def parse_wechat_page(
    body: str,
    url: str,
    account: dict[str, Any],
    fallback_date: str | None,
    tracking: dict[str, dict[str, list[str]]],
) -> dict[str, Any] | None:
    if any(marker in body for marker in ("环境异常", "访问过于频繁", "请输入验证码")):
        return None
    parser = WeChatArticleParser()
    parser.feed(body)
    observed_account = (
        parser.meta.get("author")
        or parser.meta.get("article:author")
        or _script_value(body, ("nickname", "author"))
    )
    if not account_matches(account, observed_account):
        return None
    title = clean_text(
        parser.meta.get("og:title")
        or _script_value(body, ("msg_title",))
        or " ".join(parser.title_parts)
    )
    title = re.sub(r"\s*[-_|｜]\s*微信公众平台\s*$", "", title).strip()
    if len(title) < 6:
        return None
    canonical = normalize_url(parser.meta.get("og:url") or url)
    published_at = normalize_date(
        parser.meta.get("article:published_time")
        or _script_value(body, ("publish_time", "ct"))
    ) or fallback_date
    if not published_at:
        return None
    max_age = int(account.get("maxArticleAgeDays", 45))
    if date.fromisoformat(published_at) < datetime.now(UTC).date() - timedelta(days=max_age):
        return None
    description = (
        parser.meta.get("description")
        or parser.meta.get("og:description")
        or _script_value(body, ("msg_desc",))
    )
    content = clean_text(" ".join(parser.content_parts))
    summary = short_summary(description, content, observed_account, title)
    entity_text = f"{title} {summary} {content[:4000]}"
    sector = choose_sector(account, entity_text, tracking)
    _, companies, people = account_entities(account, sector, tracking)
    mentioned_companies = [item for item in companies if _contains_entity(entity_text, item)]
    mentioned_people = [item for item in people if _contains_entity(entity_text, item)]
    title_companies = [item for item in mentioned_companies if _contains_entity(title, item)]
    company = title_companies[0] if len(title_companies) == 1 else "科技产业"
    event_type, importance = infer_event_type(title, summary)
    source_id = f"{WECHAT_PREFIX}{account['id']}"
    result: dict[str, Any] = {
        "id": article_id(source_id, canonical),
        "sourceId": source_id,
        "title": title[:220],
        "summary": summary,
        "type": event_type,
        "region": account.get("region") if account.get("region") in VALID_REGIONS else "中国",
        "sector": sector,
        "company": company,
        "publishedAt": published_at,
        "importance": int(account.get("importance", importance)),
        "source": {
            "name": observed_account,
            "url": canonical,
            "level": account.get("sourceLevel")
            if account.get("sourceLevel") in VALID_SOURCE_LEVELS
            else "媒体报道",
            "platform": "微信",
        },
        "wechatAccount": observed_account,
        "mentionedCompanies": mentioned_companies[:16],
        "mentionedPeople": mentioned_people[:16],
        "qualityScore": 72 if content else 55,
        "qualitySignals": [
            "公众号名称与白名单匹配",
            f"识别 {len(mentioned_companies)} 家相关公司",
            f"识别 {len(mentioned_people)} 位相关人物",
        ],
        "qualityStatus": "高可信" if content else "可用",
    }
    return result


def build_index_url(account: dict[str, Any], tracking: dict[str, dict[str, list[str]]]) -> str:
    sectors = list(account.get("sectorKeywords", {})) or [account.get("defaultSector", "AI / AGI")]
    terms: list[str] = []
    for sector in sectors:
        keywords, companies, people = account_entities(account, sector, tracking)
        terms.extend([*keywords[:5], *companies[:3], *people[:2]])
    terms = unique(terms, 12)
    identity = [account.get("name", ""), account.get("accountId", "")]
    identity_query = " OR ".join(f'"{clean_text(str(item))}"' for item in identity if clean_text(str(item)))
    topic_query = " OR ".join(f'"{item}"' for item in terms)
    event_query = "发布 OR 融资 OR 投资 OR 突破 OR 合作 OR 上市 OR 量产 OR 研究"
    query = f"site:mp.weixin.qq.com/s ({identity_query}) ({topic_query}) ({event_query})"
    return f"https://www.bing.com/search?format=rss&q={quote_plus(query)}"


def _xml_local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].casefold()


def _xml_text(node: ET.Element, names: Sequence[str]) -> str:
    wanted = {name.casefold() for name in names}
    for child in node.iter():
        if _xml_local(child.tag) in wanted:
            value = clean_text(" ".join(child.itertext()))
            if value:
                return value
    return ""


def parse_index_items(body: str) -> list[tuple[str, str | None]]:
    root = ET.fromstring(body)
    result: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for node in root.iter():
        if _xml_local(node.tag) not in {"item", "entry"}:
            continue
        link = _xml_text(node, ("link",))
        if not link:
            for child in node.iter():
                if _xml_local(child.tag) == "link" and child.attrib.get("href"):
                    link = child.attrib["href"]
                    break
        normalized = normalize_url(link)
        host = (urlsplit(normalized).hostname or "").casefold()
        if host != "mp.weixin.qq.com" or normalized in seen:
            continue
        published = normalize_date(_xml_text(node, ("pubdate", "published", "updated", "date")))
        result.append((normalized, published))
        seen.add(normalized)
    return result


def crawl_account(
    account: dict[str, Any],
    settings: dict[str, Any],
    tracking: dict[str, dict[str, list[str]]],
    user_agent: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    account = dict(account)
    account.setdefault("maxArticleAgeDays", settings.get("maxArticleAgeDays", 45))
    source_id = f"{WECHAT_PREFIX}{account['id']}"
    index_url = build_index_url(account, tracking)
    scanned = 0
    failed = 0
    articles: list[dict[str, Any]] = []
    try:
        candidates = parse_index_items(fetch_text(index_url, user_agent))
        scanned = len(candidates)
        for url, fallback_date in candidates[: int(settings.get("maxItemsPerAccount", 6)) * 3]:
            try:
                parsed = parse_wechat_page(
                    fetch_text(url, user_agent), url, account, fallback_date, tracking
                )
                if parsed:
                    articles.append(parsed)
            except (HTTPError, URLError, TimeoutError, OSError, ValueError, ET.ParseError):
                failed += 1
            if len(articles) >= int(settings.get("maxItemsPerAccount", 6)):
                break
            time.sleep(0.35)
    except Exception as exc:
        return [], {
            "id": source_id,
            "name": account["name"],
            "platform": "微信",
            "status": "error",
            "scanned": scanned,
            "accepted": 0,
            "failed": max(1, failed),
            "retainedPrevious": True,
            "error": clean_text(f"{type(exc).__name__}: {exc}")[:240],
        }
    status = "ok" if articles and failed == 0 else "partial" if articles else "empty"
    return articles, {
        "id": source_id,
        "name": account["name"],
        "platform": "微信",
        "status": status,
        "scanned": scanned,
        "accepted": len(articles),
        "failed": failed,
        "retainedPrevious": not articles,
    }


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def merge_snapshot(
    payload: dict[str, Any],
    incoming: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    account_ids: set[str],
) -> dict[str, Any]:
    existing = [item for item in payload.get("articles", []) if isinstance(item, dict)]
    incoming_by_source: dict[str, list[dict[str, Any]]] = {}
    for article in incoming:
        incoming_by_source.setdefault(str(article.get("sourceId", "")), []).append(article)
    status_by_id = {str(item.get("id", "")): item for item in statuses}
    retained: list[dict[str, Any]] = []
    for article in existing:
        source_id = str(article.get("sourceId", ""))
        if source_id not in account_ids:
            retained.append(article)
            continue
        new_batch = incoming_by_source.get(source_id, [])
        if not new_batch or status_by_id.get(source_id, {}).get("status") in {"error", "empty"}:
            retained.append(article)
    combined = [*retained, *incoming]
    deduped: dict[str, dict[str, Any]] = {}
    for article in combined:
        key = normalize_url(str(article.get("source", {}).get("url", ""))) or str(article.get("id", ""))
        current = deduped.get(key)
        if not current or str(article.get("publishedAt", "")) >= str(current.get("publishedAt", "")):
            deduped[key] = article
    articles = sorted(
        deduped.values(),
        key=lambda item: (
            str(item.get("publishedAt", "")),
            int(item.get("importance", 0) or 0),
        ),
        reverse=True,
    )[:MAX_TOTAL_ARTICLES]
    old_status = [
        item
        for item in payload.get("sourceStatus", [])
        if str(item.get("id", "")) not in account_ids
    ]
    entity_companies = sum(len(item.get("mentionedCompanies", [])) for item in incoming)
    entity_people = sum(len(item.get("mentionedPeople", [])) for item in incoming)
    payload["articles"] = articles
    payload["articleCount"] = len(articles)
    payload["generatedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    payload["sourceStatus"] = sorted([*old_status, *statuses], key=lambda item: str(item.get("id", "")))
    payload["wechatIngestion"] = {
        "generatedAt": payload["generatedAt"],
        "configuredAccounts": len(account_ids),
        "acceptedArticles": len(incoming),
        "mentionedCompanyLinks": entity_companies,
        "mentionedPeopleLinks": entity_people,
        "failedAccounts": sum(1 for item in statuses if item.get("status") == "error"),
    }
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account", help="crawl one configured account id")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    config = load_json(CONFIG_PATH, {})
    accounts = [
        item
        for item in config.get("accounts", [])
        if isinstance(item, dict)
        and item.get("enabled", True) is not False
        and (not args.account or item.get("id") == args.account)
    ]
    if not accounts:
        raise SystemExit("No enabled WeChat accounts matched the request")
    for account in accounts:
        if not clean_text(str(account.get("id") or "")) or not clean_text(str(account.get("name") or "")):
            raise SystemExit("Every WeChat account requires id and name")
        if not account.get("sectorKeywords"):
            raise SystemExit(f"WeChat account {account['id']} has no sectorKeywords")
    if args.validate_only:
        print(f"Validated {len(accounts)} WeChat account configurations")
        return 0

    settings = config.get("settings", {})
    tracking = tracking_by_sector()
    user_agent = DEFAULT_USER_AGENT
    incoming: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    for index, account in enumerate(accounts):
        articles, status = crawl_account(account, settings, tracking, user_agent)
        incoming.extend(articles)
        statuses.append(status)
        print(
            f"wechat={account['id']} status={status['status']} scanned={status['scanned']} accepted={status['accepted']}"
        )
        if index + 1 < len(accounts):
            time.sleep(float(settings.get("requestIntervalSeconds", 1.2)))

    payload = load_json(OUTPUT_PATH, {"schemaVersion": 3, "articles": [], "sourceStatus": []})
    account_ids = {f"{WECHAT_PREFIX}{account['id']}" for account in accounts}
    merged = merge_snapshot(payload, incoming, statuses, account_ids)
    OUTPUT_PATH.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(merged["wechatIngestion"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
