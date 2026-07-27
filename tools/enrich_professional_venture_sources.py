#!/usr/bin/env python3
"""Enrich Chinese startup profiles from professional venture-data sources.

The module deliberately does not scrape authenticated web pages or bypass anti-bot
controls. QCC and Tianyancha are accessed only through their documented official APIs
when explicit paid-call opt-in and repository credentials are present. Jingdata is
used through publicly indexed pages only; those records remain lower-confidence until
cross-validated with an official disclosure or an authenticated database response.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    from .venture_profile_extraction import (
        AMOUNT_PATTERNS,
        DATE_PATTERN,
        ROUND_PATTERN,
        CatalogCompany,
        clean_text,
        normalize_url,
        parse_catalog,
    )
except ImportError:
    from venture_profile_extraction import (
        AMOUNT_PATTERNS,
        DATE_PATTERN,
        ROUND_PATTERN,
        CatalogCompany,
        clean_text,
        normalize_url,
        parse_catalog,
    )

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "lib" / "catalog-data.ts"
SNAPSHOT_PATH = ROOT / "public" / "data" / "venture_profiles.json"
USER_AGENT = (
    "LizeRoadOne/5.0 contact=VCIQ@users.noreply.github.com "
    "(+https://github.com/VCIQ/VCIQ.github.io)"
)
REQUEST_TIMEOUT = 15
MAX_RESPONSE_BYTES = 4_000_000
MAX_PROFESSIONAL_COMPANIES = 30

QCC_COMPANY_URL = "https://api.qichacha.com/ECIInfoVerify/GetInfo"
QCC_FINANCING_URL = "https://api.qichacha.com/CompanyFinancingSearch/GetList"
QCC_INVESTMENT_URL = "https://api.qichacha.com/InvestmentCheck/GetList"
QCC_SEARCH_PAGE = "https://www.qcc.com/web/search"
QCC_HOME = "https://www.qcc.com/"

TYC_BASE_URL = "https://open.api.tianyancha.com/services/v4/open/baseinfoV3"
TYC_HOLDER_URL = "https://open.api.tianyancha.com/services/open/ic/holderList/2.0"
TYC_HOLDER_CHANGE_URL = "https://open.api.tianyancha.com/services/open/ic/holderChange/2.0"
TYC_BENEFICIARY_URL = "https://open.api.tianyancha.com/services/open/ic/humanholding/2.0"
TYC_SEARCH_PAGE = "https://www.tianyancha.com/search"
TYC_HOME = "https://www.tianyancha.com/"

JINGDATA_HOME = "https://www.jingdata.com/"
BING_RSS = "https://www.bing.com/search?format=rss&q="

FINANCING_EVIDENCE_RE = re.compile(
    r"\b(?:funding|financing|raised|raises|series\s+[a-z0-9]+|seed round|"
    r"investment|investor|valuation)\b|(?:融资|投资|领投|跟投|估值|募资)",
    re.IGNORECASE,
)
EQUITY_CHANGE_RE = re.compile(r"股东|股权|投资人|注册资本|出资|持股", re.IGNORECASE)


def _clean(value: Any, limit: int = 600) -> str:
    return clean_text(value, limit)


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _pick(row: dict[str, Any], *keys: str, limit: int = 500) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return _clean(value, limit)
    return ""


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", "", _clean(value, 300).casefold())


def _unique_strings(values: Iterable[Any], limit: int = 30, item_limit: int = 200) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _clean(value, item_limit)
        key = _normalized_key(item)
        if not item or not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= limit:
            break
    return result


def _request_bytes(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> bytes:
    request_headers = {
        "User-Agent": os.environ.get("VENTURE_PROFILE_USER_AGENT") or USER_AGENT,
        "Accept": "application/json,text/html,application/xhtml+xml;q=0.9,*/*;q=0.7",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }
    request_headers.update(headers or {})
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise RuntimeError(f"response exceeds {MAX_RESPONSE_BYTES} bytes")
        return body


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> dict[str, Any]:
    raw = _request_bytes(url, headers=headers, timeout=timeout)
    return _dict(json.loads(raw.decode("utf-8", errors="replace")))


def fetch_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    raw = _request_bytes(url, headers=headers, timeout=timeout)
    for encoding in ("utf-8", "gb18030", "big5", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def _query_url(base: str, parameters: dict[str, Any]) -> str:
    pairs = [(key, str(value)) for key, value in parameters.items() if value not in (None, "")]
    return f"{base}?{urllib.parse.urlencode(pairs)}"


def _source_status(
    name: str,
    status: str,
    detail: str,
    url: str,
    *,
    records: int = 0,
) -> dict[str, Any]:
    return {
        "name": name,
        "status": status,
        "detail": _clean(detail, 300),
        "url": normalize_url(url) or url,
        "records": max(0, int(records)),
        "updatedAt": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def _professional_source(
    name: str,
    url: str,
    section: str,
    title: str = "",
) -> dict[str, str]:
    return {
        "name": name,
        "url": normalize_url(url) or url,
        "level": "数据库记录",
        "section": section,
        "title": _clean(title, 200),
        "publishedAt": "",
    }


def _company_reference_url(base: str, company_name: str) -> str:
    return _query_url(base, {"key": company_name})


def _qcc_headers(app_key: str, secret_key: str, timestamp: int | None = None) -> dict[str, str]:
    timespan = str(timestamp or int(time.time()))
    token = hashlib.md5(f"{app_key}{timespan}{secret_key}".encode("utf-8")).hexdigest().upper()
    return {"Token": token, "Timespan": timespan}


def _result_object(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("Result", "result", "Data", "data"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return payload


def _result_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[Any] = [
        payload.get("Data"),
        payload.get("data"),
        payload.get("Result"),
        payload.get("result"),
    ]
    result_obj = _result_object(payload)
    candidates.extend(
        result_obj.get(key)
        for key in (
            "Data",
            "data",
            "Items",
            "items",
            "Result",
            "result",
            "List",
            "list",
            "holderList",
            "holderChangeList",
        )
    )
    for candidate in candidates:
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
    return []


def parse_qcc_company(payload: dict[str, Any], company_name: str) -> dict[str, Any]:
    result = _result_object(payload)
    source_url = _company_reference_url(QCC_SEARCH_PAGE, company_name)
    shareholders: list[dict[str, Any]] = []
    for row in _list(result.get("Partners")):
        if not isinstance(row, dict):
            continue
        name = _pick(row, "StockName", "PartnerName", "Name", "name", limit=160)
        if not name:
            continue
        shareholders.append(
            {
                "name": name,
                "percent": _pick(row, "StockPercent", "Percent", "percent", limit=40),
                "subscribedCapital": _pick(
                    row,
                    "ShouldCapi",
                    "SubscribedCapital",
                    "Amount",
                    "amount",
                    limit=100,
                ),
                "paidCapital": _pick(row, "RealCapi", "PaidUpCapital", limit=100),
                "tags": _unique_strings(row.get("TagsList", []), 8, 80),
                "sourceName": "企查查",
                "sourceUrl": source_url,
            }
        )
    changes: list[dict[str, Any]] = []
    for row in _list(result.get("ChangeRecords")):
        if not isinstance(row, dict):
            continue
        item = _pick(row, "ProjectName", "ChangeItem", "item", limit=160)
        if not item or not EQUITY_CHANGE_RE.search(item):
            continue
        changes.append(
            {
                "date": _pick(row, "ChangeDate", "Date", "date", limit=30),
                "item": item,
                "before": _pick(row, "BeforeContent", "Before", "before", limit=500),
                "after": _pick(row, "AfterContent", "After", "after", limit=500),
                "sourceName": "企查查",
                "sourceUrl": source_url,
            }
        )
    beneficial_owners = [
        {
            "name": row["name"],
            "percent": _clean(
                next(
                    (
                        raw.get("FinalBenefitPercent")
                        for raw in _list(result.get("Partners"))
                        if isinstance(raw, dict)
                        and _normalized_key(raw.get("StockName")) == _normalized_key(row["name"])
                    ),
                    "",
                ),
                40,
            ),
            "sourceName": "企查查",
            "sourceUrl": source_url,
        }
        for row in shareholders
        if any(tag in {"最终受益人", "实际控制人", "大股东"} for tag in row.get("tags", []))
    ]
    return {
        "legalName": _pick(result, "Name", "CompanyName", "name", limit=200),
        "creditCode": _pick(result, "CreditCode", "creditCode", limit=80),
        "registrationStatus": _pick(result, "Status", "RegStatus", "regStatus", limit=80),
        "registeredCapital": _pick(result, "RegistCapi", "RegisteredCapital", limit=100),
        "paidUpCapital": _pick(result, "RecCap", "PaidUpCapital", limit=100),
        "legalRepresentative": _pick(result, "OperName", "LegalPersonName", limit=120),
        "shareholders": shareholders[:100],
        "beneficialOwners": beneficial_owners[:20],
        "changes": changes[:100],
        "externalInvestments": [],
        "sourceNames": ["企查查"],
        "sourceUrls": [source_url],
    }


def parse_qcc_financing(payload: dict[str, Any], company_name: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    source_page = _company_reference_url(QCC_SEARCH_PAGE, company_name)
    for row in _result_rows(payload):
        product_name = _pick(row, "ProductName", "CompanyName", "Name", limit=180) or company_name
        date = _pick(row, "Date", "FinancingDate", "date", limit=30)
        round_name = _pick(row, "Round", "FinancingRound", "round", limit=80)
        amount = _pick(row, "Amount", "FinancingAmount", "amount", limit=100)
        valuation = _pick(row, "Valuation", "valuation", limit=100)
        investors = _unique_strings(
            re.split(r"[,，、;；|/]+", _pick(row, "Investment", "Investors", "Investor", limit=1000)),
            20,
            120,
        )
        news_url = normalize_url(_pick(row, "NewsUrl", "SourceUrl", "Url", limit=1000))
        title = " ".join(value for value in (product_name, round_name, "融资") if value)
        summary_parts = [
            f"融资金额：{amount}" if amount else "",
            f"估值：{valuation}" if valuation else "",
            f"投资方：{'、'.join(investors)}" if investors else "",
        ]
        if not (date or round_name or amount or investors):
            continue
        events.append(
            {
                "date": date,
                "type": "融资",
                "title": title,
                "summary": "；".join(part for part in summary_parts if part) or title,
                "amount": amount,
                "round": round_name,
                "investors": investors,
                "sourceUrl": news_url or source_page,
                "sourceName": "企查查",
            }
        )
    return events[:30]


def parse_qcc_investments(payload: dict[str, Any], company_name: str) -> list[dict[str, Any]]:
    source_page = _company_reference_url(QCC_SEARCH_PAGE, company_name)
    rows: list[dict[str, Any]] = []
    for row in _result_rows(payload):
        target = _pick(row, "CompanyName", "Name", "InvestName", "TargetName", limit=180)
        if not target:
            continue
        rows.append(
            {
                "name": target,
                "percent": _pick(row, "Percent", "StockPercent", "FundedRatio", limit=40),
                "amount": _pick(row, "Amount", "ShouldCapi", "InvestmentAmount", limit=100),
                "registeredCapital": _pick(row, "RegistCapi", "RegisteredCapital", limit=100),
                "status": _pick(row, "Status", "RegStatus", limit=80),
                "sourceName": "企查查",
                "sourceUrl": source_page,
            }
        )
    return rows[:100]


def qcc_company_evidence(
    company: CatalogCompany,
    *,
    app_key: str,
    secret_key: str,
    include_external_investments: bool,
    fetcher: Callable[..., dict[str, Any]] = fetch_json,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    headers = _qcc_headers(app_key, secret_key)
    search_name = company.name
    company_payload = fetcher(
        _query_url(QCC_COMPANY_URL, {"key": app_key, "searchKey": search_name}),
        headers=headers,
    )
    financing_payload = fetcher(
        _query_url(
            QCC_FINANCING_URL,
            {"key": app_key, "searchKey": search_name, "pageIndex": 1, "pageSize": 20},
        ),
        headers=headers,
    )
    equity = parse_qcc_company(company_payload, search_name)
    financing = parse_qcc_financing(financing_payload, search_name)
    if include_external_investments:
        investment_payload = fetcher(
            _query_url(
                QCC_INVESTMENT_URL,
                {"key": app_key, "searchKey": search_name, "pageIndex": 1, "pageSize": 20},
            ),
            headers=headers,
        )
        equity["externalInvestments"] = parse_qcc_investments(investment_payload, search_name)
    record_count = len(equity.get("shareholders", [])) + len(equity.get("changes", [])) + len(financing)
    return (
        equity,
        financing,
        _source_status(
            "企查查",
            "success" if record_count else "no_data",
            f"官方开放平台返回 {record_count} 条融资、股东或股权变更记录。",
            _company_reference_url(QCC_SEARCH_PAGE, search_name),
            records=record_count,
        ),
    )


def parse_tyc_base(payload: dict[str, Any], company_name: str) -> dict[str, Any]:
    result = _result_object(payload)
    source_url = _company_reference_url(TYC_SEARCH_PAGE, company_name)
    return {
        "legalName": _pick(result, "name", "Name", "companyName", limit=200),
        "creditCode": _pick(result, "creditCode", "CreditCode", limit=80),
        "registrationStatus": _pick(result, "regStatus", "Status", limit=80),
        "registeredCapital": _pick(result, "regCapital", "registeredCapital", limit=100),
        "paidUpCapital": _pick(result, "actualCapital", "paidUpCapital", limit=100),
        "legalRepresentative": _pick(result, "legalPersonName", "operName", limit=120),
        "shareholders": [],
        "beneficialOwners": [],
        "changes": [],
        "externalInvestments": [],
        "sourceNames": ["天眼查"],
        "sourceUrls": [source_url],
    }


def parse_tyc_holders(payload: dict[str, Any], company_name: str) -> list[dict[str, Any]]:
    source_url = _company_reference_url(TYC_SEARCH_PAGE, company_name)
    result: list[dict[str, Any]] = []
    for row in _result_rows(payload):
        name = _pick(row, "name", "shareholderName", "investorName", "holderName", limit=160)
        if not name:
            continue
        amount = _pick(row, "amount", "capital", "subscribedAmount", limit=100)
        percent = _pick(row, "percent", "ratio", "shareholdingRatio", limit=40)
        result.append(
            {
                "name": name,
                "percent": percent,
                "subscribedCapital": amount,
                "paidCapital": _pick(row, "actualAmount", "paidAmount", limit=100),
                "tags": _unique_strings(row.get("tagList", []), 8, 80),
                "sourceName": "天眼查",
                "sourceUrl": source_url,
            }
        )
    return result[:100]


def parse_tyc_changes(payload: dict[str, Any], company_name: str) -> list[dict[str, Any]]:
    source_url = _company_reference_url(TYC_SEARCH_PAGE, company_name)
    result: list[dict[str, Any]] = []
    for row in _result_rows(payload):
        holder = _pick(row, "investorName", "holderName", "name", limit=160)
        before = _pick(row, "beforePercent", "before", "contentBefore", limit=500)
        after = _pick(row, "afterPercent", "after", "contentAfter", limit=500)
        if not (holder or before or after):
            continue
        result.append(
            {
                "date": _pick(row, "changeTime", "changeDate", "date", limit=30),
                "item": f"股权变更 · {holder}" if holder else "股权变更",
                "before": before,
                "after": after,
                "sourceName": "天眼查",
                "sourceUrl": source_url,
            }
        )
    return result[:100]


def parse_tyc_beneficiaries(payload: dict[str, Any], company_name: str) -> list[dict[str, Any]]:
    source_url = _company_reference_url(TYC_SEARCH_PAGE, company_name)
    result: list[dict[str, Any]] = []
    for row in _result_rows(payload):
        name = _pick(row, "name", "shareHolder", "humanName", limit=160)
        if not name:
            continue
        result.append(
            {
                "name": name,
                "percent": _pick(row, "percent", "totalPercent", "ratio", limit=40),
                "relationship": _pick(row, "type", "relation", "tag", limit=100),
                "sourceName": "天眼查",
                "sourceUrl": source_url,
            }
        )
    return result[:20]


def tyc_company_evidence(
    company: CatalogCompany,
    *,
    token: str,
    include_beneficiaries: bool,
    fetcher: Callable[..., dict[str, Any]] = fetch_json,
) -> tuple[dict[str, Any], dict[str, Any]]:
    headers = {"Authorization": token}
    search_name = company.name
    base_payload = fetcher(_query_url(TYC_BASE_URL, {"keyword": search_name}), headers=headers)
    holder_payload = fetcher(
        _query_url(TYC_HOLDER_URL, {"keyword": search_name, "pageNum": 1, "pageSize": 20}),
        headers=headers,
    )
    change_payload = fetcher(
        _query_url(
            TYC_HOLDER_CHANGE_URL,
            {"keyword": search_name, "pageNum": 1, "pageSize": 20},
        ),
        headers=headers,
    )
    equity = parse_tyc_base(base_payload, search_name)
    equity["shareholders"] = parse_tyc_holders(holder_payload, search_name)
    equity["changes"] = parse_tyc_changes(change_payload, search_name)
    if include_beneficiaries:
        beneficiary_payload = fetcher(
            _query_url(TYC_BENEFICIARY_URL, {"keyword": search_name, "pageNum": 1, "pageSize": 20}),
            headers=headers,
        )
        equity["beneficialOwners"] = parse_tyc_beneficiaries(beneficiary_payload, search_name)
    record_count = len(equity.get("shareholders", [])) + len(equity.get("changes", []))
    return (
        equity,
        _source_status(
            "天眼查",
            "success" if record_count else "no_data",
            f"官方开放平台返回 {record_count} 条股东或股权变更记录。",
            _company_reference_url(TYC_SEARCH_PAGE, search_name),
            records=record_count,
        ),
    )


def _strip_markup(value: Any) -> str:
    return _clean(html.unescape(re.sub(r"<[^>]+>", " ", str(value or ""))), 1000)


def _identity_matches(text: str, company: CatalogCompany) -> bool:
    haystack = _normalized_key(text)
    aliases = [_normalized_key(alias) for alias in company.aliases if len(_normalized_key(alias)) >= 3]
    return any(alias in haystack for alias in aliases)


def _event_date(text: str) -> str:
    match = DATE_PATTERN.search(text)
    if not match:
        return ""
    year, month, day = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day or '1'):02d}"


def _event_amount(text: str) -> str:
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if match:
            return _clean(match.group(0), 100)
    return ""


def discover_jingdata_financing(
    company: CatalogCompany,
    *,
    fetcher: Callable[..., str] = fetch_text,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = f'site:jingdata.com "{company.name}" (融资 OR 投资 OR 估值 OR 股权)'
    url = f"{BING_RSS}{urllib.parse.quote_plus(query)}"
    try:
        body = fetcher(url)
        root = ET.fromstring(body)
    except Exception as exc:
        return [], _source_status(
            "鲸准",
            "error",
            f"公开页面索引读取失败：{type(exc).__name__}",
            JINGDATA_HOME,
        )
    events: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in root.findall(".//item"):
        title = _strip_markup(item.findtext("title"))
        description = _strip_markup(item.findtext("description"))
        raw_link = _clean(item.findtext("link"), 1000)
        link = normalize_url(raw_link)
        host = (urllib.parse.urlsplit(link).hostname or "").casefold()
        text = f"{title} {description}"
        if (
            not link
            or not (host == "jingdata.com" or host.endswith(".jingdata.com"))
            or link.casefold() in seen
            or not _identity_matches(text, company)
            or not FINANCING_EVIDENCE_RE.search(text)
        ):
            continue
        round_match = ROUND_PATTERN.search(text)
        events.append(
            {
                "date": _event_date(text),
                "type": "融资",
                "title": title or f"{company.name}投融资数据库记录",
                "summary": description or title,
                "amount": _event_amount(text),
                "round": _clean(round_match.group(0), 80) if round_match else "",
                "investors": [],
                "sourceUrl": link,
                "sourceName": "鲸准",
                "verification": "待交叉验证",
            }
        )
        seen.add(link.casefold())
        if len(events) >= 8:
            break
    return events, _source_status(
        "鲸准",
        "success" if events else "no_data",
        (
            f"从公开索引发现 {len(events)} 条可直接打开的鲸准投融资页面；"
            "未登录、未绕过验证码，数据库记录需与原始披露交叉验证。"
        ),
        JINGDATA_HOME,
        records=len(events),
    )


def _merge_named_rows(
    existing: Sequence[Any],
    additions: Sequence[Any],
    *,
    name_field: str = "name",
    limit: int = 100,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    index: dict[str, int] = {}
    for raw in [*existing, *additions]:
        if not isinstance(raw, dict):
            continue
        name = _clean(raw.get(name_field), 180)
        if not name:
            continue
        key = _normalized_key(name)
        row = {key_name: value for key_name, value in raw.items() if value not in (None, "", [], {})}
        row[name_field] = name
        if key in index:
            target = result[index[key]]
            for field, value in row.items():
                if field not in target or target[field] in (None, "", [], {}):
                    target[field] = value
            source_names = _unique_strings(
                [target.get("sourceName"), row.get("sourceName")], 4, 80
            )
            if source_names:
                target["sourceName"] = " / ".join(source_names)
            continue
        index[key] = len(result)
        result.append(row)
        if len(result) >= limit:
            break
    return result


def _merge_changes(existing: Sequence[Any], additions: Sequence[Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in [*existing, *additions]:
        if not isinstance(raw, dict):
            continue
        key = "|".join(
            _normalized_key(raw.get(field))
            for field in ("date", "item", "before", "after")
        )
        if not key.strip("|") or key in seen:
            continue
        result.append(dict(raw))
        seen.add(key)
        if len(result) >= 100:
            break
    return result


def merge_equity_profiles(existing: Any, additions: Sequence[dict[str, Any]]) -> dict[str, Any]:
    base = dict(existing) if isinstance(existing, dict) else {}
    for addition in additions:
        if not isinstance(addition, dict):
            continue
        for field in (
            "legalName",
            "creditCode",
            "registrationStatus",
            "registeredCapital",
            "paidUpCapital",
            "legalRepresentative",
        ):
            if not base.get(field) and addition.get(field):
                base[field] = addition[field]
        base["shareholders"] = _merge_named_rows(
            _list(base.get("shareholders")),
            _list(addition.get("shareholders")),
        )
        base["beneficialOwners"] = _merge_named_rows(
            _list(base.get("beneficialOwners")),
            _list(addition.get("beneficialOwners")),
            limit=20,
        )
        base["externalInvestments"] = _merge_named_rows(
            _list(base.get("externalInvestments")),
            _list(addition.get("externalInvestments")),
        )
        base["changes"] = _merge_changes(
            _list(base.get("changes")),
            _list(addition.get("changes")),
        )
        base["sourceNames"] = _unique_strings(
            [*_list(base.get("sourceNames")), *_list(addition.get("sourceNames"))],
            8,
            80,
        )
        base["sourceUrls"] = _unique_strings(
            [*_list(base.get("sourceUrls")), *_list(addition.get("sourceUrls"))],
            12,
            1000,
        )
    source_count = len(_list(base.get("sourceNames")))
    facts = sum(
        1
        for field in (
            "legalName",
            "creditCode",
            "registrationStatus",
            "registeredCapital",
            "legalRepresentative",
        )
        if base.get(field)
    ) + len(_list(base.get("shareholders"))) + len(_list(base.get("changes")))
    base["evidenceStatus"] = (
        "cross-verified" if source_count >= 2 and facts else "single-source" if facts else "pending"
    )
    base["verifiedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    return base


def _merge_financing(existing: Any, additions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [row for row in _list(existing) if isinstance(row, dict)]
    rows.extend(row for row in additions if isinstance(row, dict))
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in sorted(
        rows,
        key=lambda value: (_clean(value.get("date"), 30), _clean(value.get("title"), 220)),
        reverse=True,
    ):
        source_url = normalize_url(row.get("sourceUrl", ""))
        title = _clean(row.get("title"), 220)
        key = f"{_clean(row.get('date'), 30)}|{_normalized_key(title)}|{source_url.casefold()}"
        if not title or not source_url or key in seen:
            continue
        result.append(
            {
                "date": _clean(row.get("date"), 30),
                "type": _clean(row.get("type"), 60) or "融资",
                "title": title,
                "summary": _clean(row.get("summary"), 520) or title,
                "amount": _clean(row.get("amount"), 100),
                "round": _clean(row.get("round"), 80),
                "investors": _unique_strings(row.get("investors", []), 20, 120),
                "sourceUrl": source_url,
            }
        )
        seen.add(key)
        if len(result) >= 30:
            break
    return result


def _merge_sources(existing: Any, additions: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in [*_list(existing), *additions]:
        if not isinstance(row, dict):
            continue
        url = normalize_url(row.get("url", ""))
        if not url or url.casefold() in seen:
            continue
        result.append(dict(row, url=url))
        seen.add(url.casefold())
        if len(result) >= 40:
            break
    return result


def enrich_company(
    company: CatalogCompany,
    profile: dict[str, Any],
    *,
    paid_enabled: bool,
    qcc_app_key: str,
    qcc_secret_key: str,
    tyc_token: str,
    public_discovery: bool,
    include_external_investments: bool,
    include_beneficiaries: bool,
    qcc_fetcher: Callable[..., dict[str, Any]] = fetch_json,
    tyc_fetcher: Callable[..., dict[str, Any]] = fetch_json,
    jingdata_fetcher: Callable[..., str] = fetch_text,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    updated = dict(profile)
    equity_additions: list[dict[str, Any]] = []
    financing_additions: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    source_additions: list[dict[str, Any]] = []

    if paid_enabled and qcc_app_key and qcc_secret_key:
        try:
            qcc_equity, qcc_financing, qcc_status = qcc_company_evidence(
                company,
                app_key=qcc_app_key,
                secret_key=qcc_secret_key,
                include_external_investments=include_external_investments,
                fetcher=qcc_fetcher,
            )
            equity_additions.append(qcc_equity)
            financing_additions.extend(qcc_financing)
            statuses.append(qcc_status)
            source_additions.append(
                _professional_source(
                    "企查查",
                    qcc_status["url"],
                    "工商股权与融资数据库",
                    f"{company.name}专业数据库核验",
                )
            )
        except Exception as exc:
            statuses.append(
                _source_status(
                    "企查查",
                    "error",
                    f"官方 API 调用失败：{type(exc).__name__}: {_clean(exc, 160)}",
                    QCC_HOME,
                )
            )
    else:
        detail = (
            "付费接口调用未启用；未抓取登录后网页。"
            if not paid_enabled
            else "未配置 QCC_APP_KEY / QCC_SECRET_KEY。"
        )
        statuses.append(_source_status("企查查", "disabled", detail, QCC_HOME))

    if paid_enabled and tyc_token:
        try:
            tyc_equity, tyc_status = tyc_company_evidence(
                company,
                token=tyc_token,
                include_beneficiaries=include_beneficiaries,
                fetcher=tyc_fetcher,
            )
            equity_additions.append(tyc_equity)
            statuses.append(tyc_status)
            source_additions.append(
                _professional_source(
                    "天眼查",
                    tyc_status["url"],
                    "工商股东与股权变更数据库",
                    f"{company.name}专业数据库核验",
                )
            )
        except Exception as exc:
            statuses.append(
                _source_status(
                    "天眼查",
                    "error",
                    f"官方 API 调用失败：{type(exc).__name__}: {_clean(exc, 160)}",
                    TYC_HOME,
                )
            )
    else:
        detail = (
            "付费接口调用未启用；未抓取登录后网页。"
            if not paid_enabled
            else "未配置 TIANYANCHA_TOKEN。"
        )
        statuses.append(_source_status("天眼查", "disabled", detail, TYC_HOME))

    if public_discovery:
        events, status = discover_jingdata_financing(company, fetcher=jingdata_fetcher)
        financing_additions.extend(events)
        statuses.append(status)
        for event in events:
            source_additions.append(
                _professional_source(
                    "鲸准",
                    event["sourceUrl"],
                    "公开投融资数据库页面",
                    event["title"],
                )
            )
    else:
        statuses.append(
            _source_status("鲸准", "disabled", "公开页面发现已关闭。", JINGDATA_HOME)
        )

    updated["equityProfile"] = merge_equity_profiles(
        updated.get("equityProfile"), equity_additions
    )
    updated["financing"] = _merge_financing(updated.get("financing"), financing_additions)
    updated["professionalSources"] = statuses
    updated["sources"] = _merge_sources(updated.get("sources"), source_additions)
    return updated, statuses


def _selected_companies(
    companies: Sequence[CatalogCompany],
    *,
    limit: int,
    selected_slugs: set[str],
) -> list[CatalogCompany]:
    result = [company for company in companies if company.region == "中国"]
    if selected_slugs:
        result = [company for company in result if company.slug in selected_slugs]
    return result[: max(0, min(limit, MAX_PROFESSIONAL_COMPANIES))]


def enrich_snapshot(
    payload: dict[str, Any],
    companies: Sequence[CatalogCompany],
    *,
    paid_enabled: bool,
    qcc_app_key: str,
    qcc_secret_key: str,
    tyc_token: str,
    public_discovery: bool,
    include_external_investments: bool,
    include_beneficiaries: bool,
    limit: int,
    selected_slugs: set[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    updated = json.loads(json.dumps(payload, ensure_ascii=False))
    profiles = _dict(updated.get("companies"))
    source_statuses: list[dict[str, Any]] = []
    processed = 0
    changed = 0
    for company in _selected_companies(
        companies, limit=limit, selected_slugs=selected_slugs
    ):
        profile = _dict(profiles.get(company.slug))
        if not profile:
            continue
        before = json.dumps(profile, ensure_ascii=False, sort_keys=True)
        enriched, statuses = enrich_company(
            company,
            profile,
            paid_enabled=paid_enabled,
            qcc_app_key=qcc_app_key,
            qcc_secret_key=qcc_secret_key,
            tyc_token=tyc_token,
            public_discovery=public_discovery,
            include_external_investments=include_external_investments,
            include_beneficiaries=include_beneficiaries,
        )
        profiles[company.slug] = enriched
        processed += 1
        changed += int(before != json.dumps(enriched, ensure_ascii=False, sort_keys=True))
        for status in statuses:
            source_statuses.append(
                {
                    "kind": "company",
                    "slug": company.slug,
                    "name": company.name,
                    **status,
                }
            )
    updated["companies"] = profiles
    updated["professionalSourceStatus"] = source_statuses
    updated["professionalSourceGeneratedAt"] = datetime.now(UTC).isoformat(timespec="seconds")
    updated["schemaVersion"] = max(3, int(updated.get("schemaVersion") or 1))
    return updated, {
        "processedCompanies": processed,
        "changedCompanies": changed,
        "paidEnabled": paid_enabled,
        "qccConfigured": bool(qcc_app_key and qcc_secret_key),
        "tianyanchaConfigured": bool(tyc_token),
        "jingdataPublicDiscovery": public_discovery,
        "professionalStatusCount": len(source_statuses),
    }


def validate_snapshot(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    profiles = _dict(payload.get("companies"))
    for slug, profile_value in profiles.items():
        profile = _dict(profile_value)
        equity = _dict(profile.get("equityProfile"))
        for shareholder in _list(equity.get("shareholders")):
            if not isinstance(shareholder, dict) or not _clean(shareholder.get("name"), 160):
                errors.append(f"{slug}: shareholder without name")
                continue
            if not normalize_url(shareholder.get("sourceUrl", "")):
                errors.append(f"{slug}: shareholder without traceable source")
        for change in _list(equity.get("changes")):
            if not isinstance(change, dict) or not normalize_url(change.get("sourceUrl", "")):
                errors.append(f"{slug}: equity change without traceable source")
        status_names: list[str] = []
        for status in _list(profile.get("professionalSources")):
            if not isinstance(status, dict):
                errors.append(f"{slug}: malformed professional source status")
                continue
            name = _clean(status.get("name"), 80)
            if not name or name in status_names:
                errors.append(f"{slug}: duplicate or empty professional source status")
            status_names.append(name)
            if not normalize_url(status.get("url", "")):
                errors.append(f"{slug}: professional source without public URL")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT_PATH)
    parser.add_argument("--catalog", type=Path, default=CATALOG_PATH)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--max-companies", type=int, default=int(os.environ.get("PROFESSIONAL_SOURCE_MAX_COMPANIES", "20")))
    parser.add_argument("--company-slugs", default=os.environ.get("PROFESSIONAL_SOURCE_COMPANY_SLUGS", ""))
    args = parser.parse_args()

    payload = json.loads(args.snapshot.read_text(encoding="utf-8"))
    if args.validate_only:
        errors = validate_snapshot(payload)
        if errors:
            print(json.dumps({"passed": False, "errors": errors[:30]}, ensure_ascii=False))
            return 1
        print(json.dumps({"passed": True, "errors": []}, ensure_ascii=False))
        return 0

    companies, _institutions = parse_catalog(args.catalog.read_text(encoding="utf-8"))
    selected_slugs = {
        item.strip()
        for item in args.company_slugs.split(",")
        if item.strip()
    }
    updated, diagnostics = enrich_snapshot(
        payload,
        companies,
        paid_enabled=_truthy_env("PROFESSIONAL_SOURCE_ENABLE_PAID", False),
        qcc_app_key=os.environ.get("QCC_APP_KEY", "").strip(),
        qcc_secret_key=os.environ.get("QCC_SECRET_KEY", "").strip(),
        tyc_token=os.environ.get("TIANYANCHA_TOKEN", "").strip(),
        public_discovery=_truthy_env("PROFESSIONAL_SOURCE_PUBLIC_DISCOVERY", True),
        include_external_investments=_truthy_env(
            "PROFESSIONAL_SOURCE_INCLUDE_EXTERNAL_INVESTMENTS", False
        ),
        include_beneficiaries=_truthy_env(
            "PROFESSIONAL_SOURCE_INCLUDE_BENEFICIARIES", False
        ),
        limit=args.max_companies,
        selected_slugs=selected_slugs,
    )
    errors = validate_snapshot(updated)
    if errors:
        print(json.dumps({"passed": False, "errors": errors[:30]}, ensure_ascii=False))
        return 1
    args.snapshot.write_text(
        json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**diagnostics, "passed": True}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
