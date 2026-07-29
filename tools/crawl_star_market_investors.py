#!/usr/bin/env python3
"""Build a privacy-bounded STAR Market institutional-investor directory.

The crawler operates only on enabled A-share listings whose ticker starts with
``688``. It discovers the final IPO prospectus through CNINFO's structured
announcement endpoint, extracts text from the official PDF, and publishes:

* institutional shareholders disclosed before the IPO;
* holding facts when a table row can be parsed conservatively;
* office-level contact details explicitly disclosed for the institution;
* the issuer's public investor-relations contact as a separate field;
* exact prospectus URL and page-level evidence.

Natural-person shareholders are intentionally excluded from the public output.
Mobile numbers, identity numbers, home addresses and inferred contacts are never
published. Previous verified records are retained when the exchange or PDF is
unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

try:
    from . import cninfo_structured_disclosures as cninfo
    from . import crawl_listed_company_disclosures as listed
except ImportError:
    import cninfo_structured_disclosures as cninfo
    import crawl_listed_company_disclosures as listed

ROOT = Path(__file__).resolve().parents[1]
TRACKING_PATH = ROOT / "config" / "user_tracking.json"
CONFIG_PATH = ROOT / "config" / "star_market_investor_sources.json"
DISCLOSURE_PATH = ROOT / "public" / "data" / "listed_company_disclosures.json"
OUTPUT_PATH = ROOT / "public" / "data" / "star_market_investors.json"

SCHEMA_VERSION = 1
PROVIDER = "cninfo-prospectus"
STATIC_CNINFO_ROOT = "https://static.cninfo.com.cn/"
USER_AGENT = (
    "VCIQResearchBot/1.0 contact=VCIQ@users.noreply.github.com "
    "(+https://github.com/VCIQ/VCIQ.github.io)"
)

SHAREHOLDER_PAGE_TERMS = (
    "发行前股本结构",
    "本次发行前后股本结构",
    "发行人股东情况",
    "主要股东情况",
    "股东基本情况",
    "发行前股东",
    "前十名股东",
    "持股情况",
)

INSTITUTION_ENDINGS = (
    "合伙企业（有限合伙）",
    "合伙企业(有限合伙)",
    "股份有限公司",
    "有限责任公司",
    "资产管理有限公司",
    "投资管理有限公司",
    "股权投资基金",
    "创业投资基金",
    "产业投资基金",
    "证券投资基金",
    "投资中心（有限合伙）",
    "投资中心(有限合伙)",
    "投资合伙企业",
    "创业投资有限公司",
    "股权投资有限公司",
    "产业投资有限公司",
    "基金管理有限公司",
    "资本管理有限公司",
    "有限公司",
    "有限合伙",
    "投资基金",
    "产业基金",
    "创投基金",
    "创业投资",
    "股权投资",
    "资产管理",
    "投资中心",
    "投资公司",
    "控股集团",
    "控股公司",
    "国有资本",
    "研究院",
    "基金",
    "资本",
    "集团",
)

INSTITUTION_PATTERN = re.compile(
    r"(?P<name>[A-Za-z0-9\u4e00-\u9fff·（）()&－—-]{2,96}?(?:"
    + "|".join(re.escape(ending) for ending in INSTITUTION_ENDINGS)
    + r")(?:（有限合伙）|\(有限合伙\))?)"
)

EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LANDLINE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?0\d{2,3}[-—－\s]?\d{7,8}(?!\d)")
MOBILE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s，。；;）)]+", re.IGNORECASE)
PERCENT_PATTERN = re.compile(r"(?<!\d)(\d{1,3}(?:\.\d{1,6})?)\s*%")
SHARES_PATTERN = re.compile(r"(?<!\d)([\d,]+(?:\.\d+)?)\s*(万)?\s*股")

BLOCKED_NAME_FRAGMENTS = (
    "招股说明书",
    "发行人",
    "本公司",
    "股东名称",
    "序号",
    "保荐机构",
    "主承销商",
    "律师事务所",
    "会计师事务所",
    "资产评估",
    "证券登记",
    "上海证券交易所",
    "中国证券监督管理委员会",
)

CONTACT_LABELS = (
    "注册地址",
    "住所",
    "主要经营场所",
    "办公地址",
    "联系地址",
    "联系电话",
    "电话",
    "电子邮箱",
    "邮箱",
    "互联网网址",
    "公司网址",
    "网站",
)


@dataclass(frozen=True)
class PdfPage:
    number: int
    text: str


@dataclass(frozen=True)
class ProspectusCandidate:
    title: str
    url: str
    published_at: str
    announcement_id: str
    score: int


def clean_text(value: Any, limit: int = 2000) -> str:
    text = str(value or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" |_-—")[:limit]


def normalized_name(value: str) -> str:
    return re.sub(
        r"[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'\"“”‘’_\-/\\&+－—]",
        "",
        clean_text(value, 200).casefold(),
    )


def redact_private_text(value: Any, limit: int = 2000) -> str:
    text = clean_text(value, limit * 2)
    text = MOBILE_PATTERN.sub("[已移除手机号码]", text)
    text = IDENTITY_PATTERN.sub("[已移除身份证件信息]", text)
    return clean_text(text, limit)


def load_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    payload = load_json(path, {})
    if int(payload.get("schemaVersion", 0)) != SCHEMA_VERSION:
        raise ValueError("unsupported STAR investor config schema")
    if not isinstance(payload.get("settings"), dict):
        raise ValueError("STAR investor config requires settings")
    return payload


def load_star_listings(
    tracking_path: Path = TRACKING_PATH,
    config_path: Path = CONFIG_PATH,
) -> list[listed.Listing]:
    tracking = load_json(tracking_path, {})
    config = load_config(config_path)
    rows = [
        row
        for row in tracking.get("listedCompanies", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market") == "A股"
        and str(row.get("ticker", "")).startswith("688")
    ]
    rows.extend(
        row
        for row in config.get("extraListings", [])
        if isinstance(row, dict)
        and row.get("enabled", True) is not False
        and row.get("market", "A股") == "A股"
        and str(row.get("ticker", "")).startswith("688")
    )

    result: list[listed.Listing] = []
    seen: set[str] = set()
    for row in rows:
        ticker = listed.normalize_ticker("A股", row.get("ticker"))
        item = listed.Listing(
            catalog_slug=clean_text(row.get("catalogSlug"), 80),
            name=clean_text(row.get("name"), 120),
            market="A股",
            ticker=ticker,
            sector=clean_text(row.get("sector"), 80),
            listing_role=clean_text(row.get("listingRole", "primary"), 20) or "primary",
        )
        if not all((item.catalog_slug, item.name, item.ticker, item.sector)):
            raise ValueError(f"incomplete STAR Market listing row: {row}")
        if item.ticker in seen:
            continue
        seen.add(item.ticker)
        result.append(item)
    return sorted(result, key=lambda item: item.ticker)


def prospectus_title_score(title: str) -> int:
    value = clean_text(title, 600)
    if "招股说明书" not in value:
        return -10_000
    score = 20
    if "首次公开发行" in value:
        score += 35
    if "科创板" in value:
        score += 20
    if value.endswith("招股说明书") or value.endswith("招股说明书.pdf"):
        score += 15
    if "全文" in value:
        score += 4
    for penalty, amount in (
        ("摘要", 80),
        ("注册稿", 40),
        ("申报稿", 45),
        ("上会稿", 45),
        ("问询", 70),
        ("提示性公告", 90),
        ("更正", 8),
    ):
        if penalty in value:
            score -= amount
    return score


def prospectus_query_form(
    ticker: str,
    org_id: str,
    *,
    page_num: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "pageNum": max(1, page_num),
        "pageSize": max(1, min(page_size, 30)),
        "column": "sse",
        "tabName": "fulltext",
        "plate": "kcb",
        "stock": f"{ticker},{org_id}",
        "searchkey": "招股说明书",
        "secid": "",
        "category": "",
        "trade": "",
        "seDate": f"1990-01-01~{date.today().isoformat()}",
        "sortName": "time",
        "sortType": "desc",
        "isHLtitle": "true",
    }


def query_cninfo_prospectuses(
    listing: listed.Listing,
    org_id: str,
    settings: dict[str, Any],
) -> list[ProspectusCandidate]:
    timeout = int(settings.get("requestTimeout", 24))
    attempts = int(settings.get("requestAttempts", 2))
    max_pages = max(1, min(int(settings.get("maxQueryPages", 8)), 12))
    candidates: dict[str, ProspectusCandidate] = {}

    for page_num in range(1, max_pages + 1):
        payload = cninfo.fetch_json(
            cninfo.QUERY_URL,
            form=prospectus_query_form(
                listing.ticker,
                org_id,
                page_num=page_num,
                page_size=30,
            ),
            timeout=timeout,
            attempts=attempts,
        )
        rows = payload.get("announcements", [])
        if not isinstance(rows, list):
            break
        for row in rows:
            if not isinstance(row, dict):
                continue
            code = listed.normalize_ticker("A股", row.get("secCode"))
            if code and code != listing.ticker:
                continue
            title = clean_text(row.get("announcementTitle"), 600)
            score = prospectus_title_score(title)
            if score < 0:
                continue
            adjunct = clean_text(row.get("adjunctUrl"), 1400).lstrip("/")
            if not adjunct:
                continue
            url = STATIC_CNINFO_ROOT + adjunct
            published_at = cninfo._announcement_date(row)
            announcement_id = clean_text(row.get("announcementId"), 100)
            candidates[url] = ProspectusCandidate(
                title=title,
                url=url,
                published_at=published_at,
                announcement_id=announcement_id,
                score=score,
            )
        if payload.get("hasMore") is not True:
            break

    return sorted(
        candidates.values(),
        key=lambda item: (item.score, item.published_at, item.url),
        reverse=True,
    )


def existing_prospectus_candidate(
    listing: listed.Listing,
    disclosure_path: Path = DISCLOSURE_PATH,
) -> ProspectusCandidate | None:
    snapshot = load_json(disclosure_path, {})
    company = snapshot.get("companies", {}).get(listing.catalog_slug, {})
    events = company.get("events", []) if isinstance(company, dict) else []
    candidates: list[ProspectusCandidate] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        title = clean_text(event.get("title"), 600)
        score = prospectus_title_score(title)
        source = event.get("source") if isinstance(event.get("source"), dict) else {}
        url = clean_text(source.get("url"), 1400)
        if score < 0 or not url:
            continue
        candidates.append(
            ProspectusCandidate(
                title=title,
                url=url,
                published_at=clean_text(event.get("publishedAt"), 20),
                announcement_id=clean_text(event.get("id"), 100),
                score=score,
            )
        )
    return max(candidates, key=lambda item: (item.score, item.published_at), default=None)


def resolve_prospectus(
    listing: listed.Listing,
    config: dict[str, Any],
    org_ids: dict[str, str],
) -> ProspectusCandidate:
    override = config.get("overrides", {}).get(listing.catalog_slug, {})
    if isinstance(override, dict) and override.get("prospectusUrl"):
        title = clean_text(
            override.get("title") or f"{listing.name}首次公开发行股票招股说明书",
            600,
        )
        return ProspectusCandidate(
            title=title,
            url=clean_text(override.get("prospectusUrl"), 1400),
            published_at=clean_text(override.get("publishedAt"), 20),
            announcement_id="config-override",
            score=10_000,
        )

    org_id = org_ids.get(listing.ticker, "")
    errors: list[str] = []
    if org_id:
        try:
            candidates = query_cninfo_prospectuses(listing, org_id, config["settings"])
            if candidates:
                return candidates[0]
        except Exception as exc:  # noqa: BLE001 - fallback to retained metadata.
            errors.append(f"CNINFO:{type(exc).__name__}:{exc}")
    existing = existing_prospectus_candidate(listing)
    if existing:
        return existing
    detail = "; ".join(errors) if errors else "no final prospectus candidate"
    raise RuntimeError(f"prospectus discovery failed for {listing.ticker}: {detail}")


def download_pdf(url: str, settings: dict[str, Any]) -> bytes:
    host = (urlsplit(url).hostname or "").casefold()
    if not (host.endswith("cninfo.com.cn") or host.endswith("sse.com.cn")):
        raise ValueError(f"unapproved prospectus host: {host}")
    timeout = int(settings.get("requestTimeout", 24))
    attempts = max(1, min(int(settings.get("requestAttempts", 2)), 3))
    max_bytes = max(1_000_000, min(int(settings.get("maxPdfBytes", 52_428_800)), 100_000_000))
    last_error: Exception | None = None
    for attempt in range(attempts):
        request = Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.5",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.6",
                "Accept-Encoding": "identity",
                "Referer": "https://www.cninfo.com.cn/",
            },
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                chunks: list[bytes] = []
                size = 0
                while True:
                    chunk = response.read(min(1_048_576, max_bytes - size + 1))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(f"prospectus exceeds maxPdfBytes={max_bytes}")
                payload = b"".join(chunks)
                if not payload.startswith(b"%PDF"):
                    raise ValueError("prospectus response is not a PDF")
                return payload
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"PDF download failed for {url}: {last_error}")


def extract_pdf_pages(payload: bytes, max_pages: int) -> tuple[list[PdfPage], int]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - dedicated workflow installs it.
        raise RuntimeError("pypdf is required; install requirements-star-investors.txt") from exc

    reader = PdfReader(io.BytesIO(payload), strict=False)
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception:  # noqa: BLE001 - extraction may still work page by page.
            pass
    page_count = len(reader.pages)
    limit = max(1, min(max_pages, page_count))
    pages: list[PdfPage] = []
    for index in range(limit):
        try:
            text = reader.pages[index].extract_text() or ""
        except Exception:  # noqa: BLE001 - one malformed page must not abort the file.
            text = ""
        cleaned = clean_text(text, 200_000)
        if cleaned:
            pages.append(PdfPage(number=index + 1, text=cleaned))
    return pages, page_count


def _context(text: str, start: int, width: int = 520) -> str:
    return clean_text(text[max(0, start - width) : start + width], width * 2)


def _safe_landline(value: str) -> str:
    match = LANDLINE_PATTERN.search(value)
    if not match:
        return ""
    result = re.sub(r"\s+", "", match.group(0)).replace("—", "-").replace("－", "-")
    return "" if MOBILE_PATTERN.search(result) else result


def _safe_email(value: str) -> str:
    match = EMAIL_PATTERN.search(value)
    return match.group(0).lower() if match else ""


def _safe_website(value: str) -> str:
    match = URL_PATTERN.search(value)
    if not match:
        return ""
    result = match.group(0).rstrip(".,，。；;）)")
    return "https://" + result if result.startswith("www.") else result


def _extract_labeled_value(text: str, labels: Iterable[str], limit: int = 140) -> str:
    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in CONTACT_LABELS)
    match = re.search(
        rf"(?:{label_pattern})\s*[：:]?\s*(?P<value>.{{3,{limit}}}?)(?=(?:{stop_pattern})\s*[：:]|\n|$)",
        text,
        re.DOTALL,
    )
    if not match:
        return ""
    value = clean_text(match.group("value"), limit)
    value = MOBILE_PATTERN.sub("", value)
    value = IDENTITY_PATTERN.sub("", value)
    return value.strip(" ：:，,；;")


def extract_issuer_contact(pages: list[PdfPage], company_name: str) -> dict[str, Any]:
    best: tuple[int, PdfPage, str] | None = None
    for page in pages:
        text = page.text
        score = 0
        if company_name in text:
            score += 4
        if "发行人" in text:
            score += 3
        if "联系电话" in text or "电子邮箱" in text:
            score += 3
        if "有关中介机构" in text or "本次发行有关" in text:
            score += 2
        if score < 5:
            continue
        if best is None or score > best[0]:
            best = (score, page, text)
    if best is None:
        return {}

    _, page, text = best
    company_position = text.find(company_name)
    block = _context(text, company_position if company_position >= 0 else 0, 1000)
    email = _safe_email(block)
    phone = _safe_landline(block)
    website = _safe_website(block)
    address = _extract_labeled_value(
        block,
        ("联系地址", "办公地址", "住所", "注册地址"),
        180,
    )
    contact = {
        key: value
        for key, value in {
            "phone": phone,
            "email": email,
            "website": website,
            "officeAddress": address,
        }.items()
        if value
    }
    if contact:
        contact["sourcePage"] = page.number
        contact["scope"] = "上市公司公开投资者关系联系方式"
    return contact


def evidence_for_match(text: str, start: int, end: int, limit: int = 220) -> str:
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end < 0:
        line_end = len(text)
    line = clean_text(text[line_start:line_end], limit * 2)
    if line and len(line) <= limit * 2:
        return redact_private_text(line, limit)
    return redact_private_text(text[start : min(len(text), end + limit)], limit)


def _candidate_name(raw: str, company_name: str) -> str:
    value = clean_text(raw, 120)
    value = re.sub(r"^\d+[、.．)）]?", "", value).strip()
    value = re.sub(r"^(股东|名称|机构股东)", "", value).strip(" ：:")
    if not value or len(value) < 3 or len(value) > 100:
        return ""
    if normalized_name(value) == normalized_name(company_name):
        return ""
    if any(fragment in value for fragment in BLOCKED_NAME_FRAGMENTS):
        return ""
    if re.fullmatch(r"[A-Za-z]+", value) and len(value) < 5:
        return ""
    return value


def classify_investor(name: str, context: str) -> str:
    combined = f"{name} {context}"
    if any(term in combined for term in ("员工持股", "员工平台", "员工持股平台")):
        return "员工持股平台"
    if any(term in combined for term in ("国资", "国有资本", "国投", "国新", "产业引导基金", "政府投资")):
        return "国资投资平台"
    if any(term in combined for term in ("创业投资", "创投", "股权投资", "投资基金", "资本管理", "基金管理")):
        return "股权投资机构"
    if any(term in name for term in ("产业投资", "控股集团", "科技集团", "实业集团", "股份有限公司")):
        return "产业投资者"
    if "合伙企业" in name or "有限合伙" in name:
        return "投资合伙企业"
    return "其他机构股东"


def extract_holding(context: str) -> tuple[float | None, float | None]:
    ownership: float | None = None
    shares: float | None = None
    percent = PERCENT_PATTERN.search(context)
    if percent:
        try:
            candidate = float(percent.group(1))
            if 0 < candidate <= 100:
                ownership = candidate
        except ValueError:
            pass
    share_match = SHARES_PATTERN.search(context)
    if share_match:
        try:
            candidate = float(share_match.group(1).replace(",", ""))
            if share_match.group(2):
                candidate *= 10_000
            if candidate > 0:
                shares = candidate
        except ValueError:
            pass
    return shares, ownership


def extract_investor_contact(pages: list[PdfPage], name: str) -> dict[str, Any]:
    for page in pages:
        position = page.text.find(name)
        if position < 0:
            continue
        block = _context(page.text, position, 700)
        if not any(label in block for label in CONTACT_LABELS):
            continue
        address = _extract_labeled_value(
            block,
            ("注册地址", "住所", "主要经营场所", "办公地址"),
            180,
        )
        phone = _safe_landline(block)
        email = _safe_email(block)
        website = _safe_website(block)
        contact = {
            key: value
            for key, value in {
                "officeAddress": address,
                "phone": phone,
                "email": email,
                "website": website,
            }.items()
            if value
        }
        if contact:
            contact["sourcePage"] = page.number
            contact["scope"] = "招股说明书公开的机构级联系方式"
            return contact
    return {}


def extract_institutional_investors(
    pages: list[PdfPage],
    company_name: str,
    *,
    max_investors: int,
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}
    likely_pages = [
        page
        for page in pages
        if any(term in page.text for term in SHAREHOLDER_PAGE_TERMS)
    ]
    for page in likely_pages:
        for match in INSTITUTION_PATTERN.finditer(page.text):
            name = _candidate_name(match.group("name"), company_name)
            if not name:
                continue
            context = _context(page.text, match.start(), 260)
            # Do not treat intermediary rosters as shareholder evidence.
            if any(term in context for term in ("保荐机构（主承销商）", "发行人律师", "审计机构")) and not any(
                term in context for term in SHAREHOLDER_PAGE_TERMS
            ):
                continue
            key = normalized_name(name)
            if not key:
                continue
            shares, ownership = extract_holding(context)
            item = {
                "id": "star-investor-" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:18],
                "name": name,
                "normalizedName": key,
                "institutional": True,
                "investorType": classify_investor(name, context),
                "sourcePage": page.number,
                "sourceSection": next(
                    (term for term in SHAREHOLDER_PAGE_TERMS if term in page.text),
                    "股东情况",
                ),
                "evidence": evidence_for_match(page.text, match.start(), match.end(), 220),
            }
            if shares is not None:
                item["preIpoShares"] = round(shares, 4)
            if ownership is not None:
                item["preIpoOwnershipPct"] = round(ownership, 6)
            current = candidates.get(key)
            current_quality = int(current is not None) + int(bool(current and "preIpoOwnershipPct" in current))
            next_quality = 1 + int("preIpoOwnershipPct" in item)
            if current is None or next_quality > current_quality:
                candidates[key] = item

    result: list[dict[str, Any]] = []
    for item in candidates.values():
        contact = extract_investor_contact(pages, item["name"])
        if contact:
            item["publicContact"] = contact
            item["contactStatus"] = "prospectus-public"
        else:
            item["contactStatus"] = "not-disclosed-in-prospectus"
        result.append(item)

    result.sort(
        key=lambda item: (
            -float(item.get("preIpoOwnershipPct", -1)),
            -float(item.get("preIpoShares", -1)),
            item["name"],
        )
    )
    return result[: max(1, max_investors)]


def _official_prospectus_host(url: str) -> bool:
    host = (urlsplit(url).hostname or "").casefold()
    return host.endswith("cninfo.com.cn") or host.endswith("sse.com.cn")


def build_company_record(
    listing: listed.Listing,
    candidate: ProspectusCandidate,
    config: dict[str, Any],
) -> dict[str, Any]:
    settings = config["settings"]
    payload = download_pdf(candidate.url, settings)
    pages, page_count = extract_pdf_pages(
        payload,
        max_pages=max(1, min(int(settings.get("maxPages", 1200)), 2000)),
    )
    if not pages:
        raise RuntimeError("prospectus contains no extractable text; OCR is intentionally disabled")
    investors = extract_institutional_investors(
        pages,
        listing.name,
        max_investors=max(1, min(int(settings.get("maxInvestorsPerCompany", 120)), 300)),
    )
    issuer_contact = extract_issuer_contact(pages, listing.name)
    minimum = max(0, int(settings.get("minimumInvestorsPerCompany", 1)))
    status = "ok" if len(investors) >= minimum else "partial"
    errors = [] if status == "ok" else [f"only {len(investors)} institutional investors extracted"]
    return {
        "slug": listing.catalog_slug,
        "name": listing.name,
        "ticker": listing.ticker,
        "exchange": "上海证券交易所科创板",
        "sector": listing.sector,
        "updatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "status": status,
        "prospectus": {
            "title": candidate.title,
            "url": candidate.url,
            "publishedAt": candidate.published_at,
            "announcementId": candidate.announcement_id,
            "pageCount": page_count,
            "textPageCount": len(pages),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "provider": PROVIDER,
        },
        "issuerInvestorRelations": issuer_contact,
        "institutionalInvestorCount": len(investors),
        "naturalPersonContactsPublished": False,
        "investors": investors,
        "errors": errors,
    }


def public_human_text(snapshot: dict[str, Any]) -> str:
    segments: list[str] = []
    companies = snapshot.get("companies", {})
    if not isinstance(companies, dict):
        return ""
    for company in companies.values():
        if not isinstance(company, dict):
            continue
        for key in ("name", "exchange", "sector"):
            value = company.get(key)
            if isinstance(value, str):
                segments.append(value)
        prospectus = company.get("prospectus")
        if isinstance(prospectus, dict) and isinstance(prospectus.get("title"), str):
            segments.append(prospectus["title"])
        issuer_contact = company.get("issuerInvestorRelations")
        if isinstance(issuer_contact, dict):
            segments.extend(
                value
                for key, value in issuer_contact.items()
                if key != "sourcePage" and isinstance(value, str)
            )
        investors = company.get("investors")
        if not isinstance(investors, list):
            continue
        for investor in investors:
            if not isinstance(investor, dict):
                continue
            for key in ("name", "investorType", "sourceSection", "evidence"):
                value = investor.get(key)
                if isinstance(value, str):
                    segments.append(value)
            contact = investor.get("publicContact")
            if isinstance(contact, dict):
                segments.extend(
                    value
                    for key, value in contact.items()
                    if key != "sourcePage" and isinstance(value, str)
                )
    return "\n".join(segments)


def validate_snapshot(snapshot: dict[str, Any], *, require_companies: bool = False) -> list[str]:
    errors: list[str] = []
    if int(snapshot.get("schemaVersion", 0)) != SCHEMA_VERSION:
        errors.append("unsupported schemaVersion")
    companies = snapshot.get("companies")
    if not isinstance(companies, dict):
        return [*errors, "companies must be an object"]
    if require_companies and not companies:
        errors.append("no STAR Market company records")

    investor_count = 0
    human_text = public_human_text(snapshot)
    if MOBILE_PATTERN.search(human_text):
        errors.append("mobile number detected in public snapshot")
    if IDENTITY_PATTERN.search(human_text):
        errors.append("identity number detected in public snapshot")

    for slug, company in companies.items():
        if not isinstance(company, dict):
            errors.append(f"{slug}: invalid company record")
            continue
        ticker = str(company.get("ticker", ""))
        if not re.fullmatch(r"688\d{3}", ticker):
            errors.append(f"{slug}: non-STAR ticker {ticker}")
        prospectus = company.get("prospectus") if isinstance(company.get("prospectus"), dict) else {}
        if not _official_prospectus_host(str(prospectus.get("url", ""))):
            errors.append(f"{slug}: prospectus URL is not official")
        investors = company.get("investors")
        if not isinstance(investors, list):
            errors.append(f"{slug}: investors must be an array")
            continue
        seen: set[str] = set()
        for investor in investors:
            if not isinstance(investor, dict):
                errors.append(f"{slug}: invalid investor record")
                continue
            name = clean_text(investor.get("name"), 120)
            key = normalized_name(name)
            if not name or not key:
                errors.append(f"{slug}: investor missing name")
                continue
            if key in seen:
                errors.append(f"{slug}: duplicate investor {name}")
            seen.add(key)
            if investor.get("institutional") is not True:
                errors.append(f"{slug}: non-institutional record published for {name}")
            if int(investor.get("sourcePage", 0)) <= 0:
                errors.append(f"{slug}: investor {name} missing source page")
            investor_count += 1

    if int(snapshot.get("companyCount", -1)) != len(companies):
        errors.append("companyCount mismatch")
    if int(snapshot.get("investorCount", -1)) != investor_count:
        errors.append("investorCount mismatch")
    return errors


def build_snapshot(
    *,
    listing_filter: str = "",
    config_path: Path = CONFIG_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict[str, Any]:
    config = load_config(config_path)
    listings = load_star_listings(config_path=config_path)
    if listing_filter:
        listings = [
            item
            for item in listings
            if item.ticker == listing_filter or item.catalog_slug == listing_filter
        ]
    previous = load_json(output_path, {})
    previous_companies = previous.get("companies", {}) if isinstance(previous, dict) else {}
    stock_payload = cninfo.fetch_json(
        cninfo.STOCK_LIST_URL,
        timeout=int(config["settings"].get("requestTimeout", 24)),
        attempts=int(config["settings"].get("requestAttempts", 2)),
    )
    org_ids = cninfo.parse_org_ids(stock_payload)
    companies: dict[str, Any] = {}
    source_status: list[dict[str, Any]] = []

    for listing in listings:
        started = time.monotonic()
        try:
            candidate = resolve_prospectus(listing, config, org_ids)
            record = build_company_record(listing, candidate, config)
            companies[listing.catalog_slug] = record
            source_status.append(
                {
                    "id": f"star-prospectus-{listing.ticker}",
                    "companySlug": listing.catalog_slug,
                    "ticker": listing.ticker,
                    "status": record["status"],
                    "investorCount": record["institutionalInvestorCount"],
                    "retainedPrevious": False,
                    "durationMs": round((time.monotonic() - started) * 1000),
                    "errors": record["errors"],
                }
            )
        except Exception as exc:  # noqa: BLE001 - retain the last verified record.
            previous_record = previous_companies.get(listing.catalog_slug)
            if isinstance(previous_record, dict) and previous_record.get("investors"):
                retained = json.loads(json.dumps(previous_record, ensure_ascii=False))
                retained["status"] = "retained"
                retained["errors"] = [f"{type(exc).__name__}:{exc}"]
                companies[listing.catalog_slug] = retained
                status = "retained"
            else:
                status = "error"
            source_status.append(
                {
                    "id": f"star-prospectus-{listing.ticker}",
                    "companySlug": listing.catalog_slug,
                    "ticker": listing.ticker,
                    "status": status,
                    "investorCount": len(companies.get(listing.catalog_slug, {}).get("investors", [])),
                    "retainedPrevious": status == "retained",
                    "durationMs": round((time.monotonic() - started) * 1000),
                    "errors": [f"{type(exc).__name__}:{exc}"],
                }
            )

    investor_count = sum(
        len(company.get("investors", []))
        for company in companies.values()
        if isinstance(company, dict)
    )
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "companyCount": len(companies),
        "investorCount": investor_count,
        "scope": {
            "market": "上海证券交易所科创板",
            "listingRule": "enabled A-share listings with 688xxx ticker",
            "shareholderRule": "institutional shareholders disclosed in the IPO prospectus",
        },
        "privacy": {
            "naturalPersonShareholdersExcluded": True,
            "personalPhonesExcluded": True,
            "identityNumbersExcluded": True,
            "contacts": "Only organization-level contact details explicitly disclosed in the prospectus are published.",
        },
        "methodology": {
            "prospectusProvider": "CNINFO structured announcements with official PDF URLs",
            "pdfExtraction": "pypdf text extraction; OCR and access-control bypass are not used",
            "retention": "previous verified company record retained on source failure",
        },
        "companies": companies,
        "sourceStatus": source_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate the current snapshot")
    parser.add_argument("--require-companies", action="store_true")
    parser.add_argument("--listing", default="", help="ticker or catalog slug")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    if args.check:
        snapshot = load_json(args.output, {})
        errors = validate_snapshot(snapshot, require_companies=args.require_companies)
        if errors:
            raise SystemExit("STAR investor snapshot invalid:\n- " + "\n- ".join(errors))
        print(
            json.dumps(
                {
                    "valid": True,
                    "companyCount": snapshot.get("companyCount", 0),
                    "investorCount": snapshot.get("investorCount", 0),
                },
                ensure_ascii=False,
            )
        )
        return 0

    snapshot = build_snapshot(listing_filter=args.listing, output_path=args.output)
    errors = validate_snapshot(snapshot, require_companies=args.require_companies)
    if errors:
        raise SystemExit("generated STAR investor snapshot invalid:\n- " + "\n- ".join(errors))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "companyCount": snapshot["companyCount"],
                "investorCount": snapshot["investorCount"],
                "sourceStatus": snapshot["sourceStatus"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
