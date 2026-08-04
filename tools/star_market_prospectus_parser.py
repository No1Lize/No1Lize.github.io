#!/usr/bin/env python3
"""Conservative parser for institutional shareholders in STAR Market prospectuses.

Only explicit pre-IPO shareholder table rows are eligible for publication. The
parser resolves abbreviations through the prospectus definitions section or an
exact shareholder basic-information block. Narrative mentions, intermediary
rosters, underlying fund partners and natural persons are deliberately ignored.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Iterable, Protocol


class PageLike(Protocol):
    number: int
    text: str


@dataclass(frozen=True)
class ShareholderRow:
    rank: int
    disclosed_name: str
    pre_ipo_shares: float
    pre_ipo_ownership_pct: float
    page: int
    evidence: str
    section: str
    priority: int


@dataclass(frozen=True)
class BasicInformation:
    disclosed_name: str
    full_name: str
    page: int
    office_address: str = ""
    phone: str = ""
    email: str = ""
    website: str = ""


PRIMARY_TABLE_MARKERS = (
    "本次发行前",
    "本次发行后",
    "股东名称",
    "持股数",
)
FALLBACK_TABLE_MARKERS = (
    "本次发行前",
    "股东名称",
    "股份",
    "比例",
)

ROW_PATTERN = re.compile(
    r"^\s*(?P<rank>\d{1,3})\s+"
    r"(?P<name>.+?)\s+"
    r"(?P<pre_shares>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<pre_pct>\d{1,3}(?:\.\d+)?)\s*%?"
    r"(?:\s+(?P<post_shares>\d[\d,]*(?:\.\d+)?)\s+"
    r"(?P<post_pct>\d{1,3}(?:\.\d+)?)\s*%?)?"
    r"(?:\s+.*招股说明书)?\s*$"
)

MOBILE_PATTERN = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
IDENTITY_PATTERN = re.compile(r"(?<!\d)\d{17}[0-9Xx](?!\d)")
EMAIL_PATTERN = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
LANDLINE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?0\d{2,3}[-—－\s]?\d{7,8}(?!\d)")
URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s，。；;）)]+", re.IGNORECASE)

INSTITUTION_HINTS = (
    "有限公司",
    "有限责任公司",
    "股份有限公司",
    "合伙企业",
    "有限合伙",
    "投资",
    "基金",
    "资本",
    "创投",
    "资产管理",
    "企业管理",
    "科技中心",
    "研究院",
    "集团",
    "控股",
    "讯飞",
    "招银",
    "国投",
    "国新",
    "中金",
    "国科",
    "联想",
    "阿里",
    "算源",
    "图灵",
)

LEGAL_SUFFIXES = (
    "合伙企业（有限合伙）",
    "合伙企业(有限合伙)",
    "投资企业（有限合伙）",
    "投资企业(有限合伙)",
    "投资中心（有限合伙）",
    "投资中心(有限合伙)",
    "管理中心（有限合伙）",
    "管理中心(有限合伙)",
    "股份有限公司",
    "有限责任公司",
    "有限公司",
    "研究院有限公司",
)

NARRATIVE_NAME_FRAGMENTS = (
    "整体变更",
    "变更为股份有限公司",
    "事务合伙人为",
    "执行事务合伙人为",
    "普通合伙人为",
    "合伙人为",
    "董事长",
    "总经理",
    "担任",
    "股东名称",
    "发行人",
    "本公司",
    "招股说明书",
    "保荐机构",
    "主承销商",
    "律师事务所",
    "会计师事务所",
    "证券交易所",
)

GENERIC_NAMES = {
    "有限公司",
    "有限责任公司",
    "股份有限公司",
    "管理有限公司",
    "投资有限公司",
    "基金管理有限公司",
    "资本管理有限公司",
    "投资基金",
    "产业基金",
    "基金",
    "资本",
    "集团",
}

FIELD_LABELS = (
    "名称",
    "企业类型",
    "法定代表人",
    "执行事务合伙人",
    "普通合伙人",
    "住所",
    "注册地址",
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
    "注册资本",
    "认缴出资额",
    "实缴出资额",
    "统一社会信用代码",
    "注册号",
    "成立时间",
    "成立日期",
    "经营范围/主营业务",
    "经营范围",
    "主营业务",
    "主要财务数据",
    "总资产",
    "净资产",
    "净利润",
)


def clean_text(value: Any, limit: int = 2000) -> str:
    text = str(value or "")
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"[\t\r]+", " ", text)
    text = re.sub(r" +", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip(" |_-—")[:limit]


def normalize_name(value: Any) -> str:
    return re.sub(
        r"[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'\"“”‘’_\-/\\&+－—]",
        "",
        clean_text(value, 300).casefold(),
    )


def redact_private_text(value: Any, limit: int = 2000) -> str:
    text = clean_text(value, limit * 2)
    text = MOBILE_PATTERN.sub("[已移除手机号码]", text)
    text = IDENTITY_PATTERN.sub("[已移除身份证件信息]", text)
    return clean_text(text, limit)


def _display_join(parts: Iterable[str], limit: int = 300) -> str:
    value = " ".join(clean_text(part, limit) for part in parts if clean_text(part, limit))
    value = re.sub(r"(?<=[\u4e00-\u9fff（(])\s+(?=[\u4e00-\u9fff）)])", "", value)
    value = re.sub(r"\s+", " ", value)
    return clean_text(value, limit)


def _balanced_legal_name(value: str) -> bool:
    return value.count("（") == value.count("）") and value.count("(") == value.count(")")


def _strip_state_owned_marker(value: str) -> str:
    return clean_text(
        re.sub(r"\s*(?:（SS）|\(SS\)|\bSS\b)\s*$", "", value, flags=re.IGNORECASE),
        160,
    )


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _page_lines(page: PageLike) -> list[str]:
    return [clean_text(line, 1200) for line in str(page.text or "").splitlines() if clean_text(line, 1200)]


def _is_primary_table_page(text: str) -> bool:
    compact = clean_text(text, 200_000)
    return all(marker in compact for marker in PRIMARY_TABLE_MARKERS)


def _is_fallback_table_page(text: str) -> bool:
    compact = clean_text(text, 200_000)
    return all(marker in compact for marker in FALLBACK_TABLE_MARKERS) and (
        "前十名股东" in compact or "发行前股东持股" in compact
    )


def parse_shareholder_rows(pages: list[PageLike]) -> list[ShareholderRow]:
    rows: dict[str, ShareholderRow] = {}
    for page in pages:
        primary = _is_primary_table_page(page.text)
        fallback = not primary and _is_fallback_table_page(page.text)
        if not primary and not fallback:
            continue
        section = "公司本次发行前后股本情况" if primary else "本次发行前股东持股情况"
        for line in _page_lines(page):
            match = ROW_PATTERN.match(line)
            if not match:
                continue
            if primary and not match.group("post_shares"):
                # A primary table has both pre- and post-IPO columns. Requiring all
                # four values prevents partner rosters and the repeated top-ten
                # table on the same page from entering the directory.
                continue
            disclosed_name = _strip_state_owned_marker(match.group("name"))
            if not disclosed_name or disclosed_name in {"合计", "本次公开发行的股份"}:
                continue
            if any(fragment in disclosed_name for fragment in NARRATIVE_NAME_FRAGMENTS):
                continue
            try:
                shares = _number(match.group("pre_shares"))
                ownership = float(match.group("pre_pct"))
            except ValueError:
                continue
            if shares <= 0 or not (0 < ownership <= 100):
                continue
            row = ShareholderRow(
                rank=int(match.group("rank")),
                disclosed_name=disclosed_name,
                pre_ipo_shares=shares,
                pre_ipo_ownership_pct=ownership,
                page=int(page.number),
                evidence=redact_private_text(line, 260),
                section=section,
                priority=2 if primary else 1,
            )
            key = normalize_name(disclosed_name)
            current = rows.get(key)
            if current is None or row.priority > current.priority:
                rows[key] = row
    return sorted(rows.values(), key=lambda row: (row.rank, row.disclosed_name))


def _definition_full_name(value: str) -> str:
    text = _display_join([value], 500)
    text = re.sub(r"\bL\.P\s+\.", "L.P.", text, flags=re.IGNORECASE)
    text = re.split(r"[，,；;](?:曾用名|原名|英文名|现名)", text, maxsplit=1)[0]
    if "，" in text:
        text = text.split("，", 1)[0]
    return clean_text(text, 240)


def extract_definition_map(
    pages: list[PageLike],
    aliases: Iterable[str],
    *,
    max_definition_page: int = 80,
) -> dict[str, tuple[str, int]]:
    alias_list = sorted({clean_text(alias, 120) for alias in aliases if clean_text(alias, 120)}, key=len, reverse=True)
    result: dict[str, tuple[str, int]] = {}
    for page in pages:
        if int(page.number) > max_definition_page:
            continue
        lines = _page_lines(page)
        for index, line in enumerate(lines):
            for alias in alias_list:
                if alias in result:
                    continue
                match = re.match(
                    rf"^\s*{re.escape(alias)}(?:（SS）|\(SS\))?\s+指\s*(?P<tail>.*)$",
                    line,
                    flags=re.IGNORECASE,
                )
                if not match:
                    continue
                parts = [match.group("tail")]
                for following in lines[index + 1 : index + 5]:
                    if re.match(r"^\S.{0,30}\s+指(?:\s|$)", following):
                        break
                    if "首次公开发行股票" in following or re.fullmatch(r"1-1-\d+", following):
                        break
                    parts.append(following)
                    if any(suffix in _display_join(parts, 500) for suffix in LEGAL_SUFFIXES):
                        break
                full_name = _definition_full_name(_display_join(parts, 500))
                if full_name and normalize_name(full_name) != normalize_name(alias):
                    result[alias] = (full_name, int(page.number))
    return result


def _is_numbered_heading(line: str) -> bool:
    return bool(re.match(r"^\s*(?:\d{1,3}|[一二三四五六七八九十]{1,4})[、.．]\s*\S+", line))


def _truncate_inline_fields(value: str, current_labels: tuple[str, ...]) -> str:
    text = clean_text(value, 600)
    other_labels = sorted(
        (label for label in FIELD_LABELS if label not in current_labels),
        key=len,
        reverse=True,
    )
    if not other_labels:
        return text
    marker = re.search(
        r"\s+(?:" + "|".join(re.escape(label) for label in other_labels) + r")\s*[：:]?",
        text,
    )
    if marker:
        text = text[: marker.start()]
    return clean_text(text, 300)


def _field_value(block: list[tuple[int, str]], labels: tuple[str, ...], limit: int) -> tuple[str, int]:
    labels_pattern = "|".join(re.escape(label) for label in labels)
    all_labels_pattern = "|".join(re.escape(label) for label in FIELD_LABELS)
    for index, (page, line) in enumerate(block):
        match = re.match(rf"^(?:{labels_pattern})\s*[：:]?\s*(?P<value>.*)$", line)
        if not match:
            continue
        parts = [_truncate_inline_fields(match.group("value"), labels)]
        for next_page, following in block[index + 1 : index + 4]:
            if re.match(rf"^(?:{all_labels_pattern})\s*[：:]?", following):
                break
            if _is_numbered_heading(following):
                break
            if "首次公开发行股票" in following or re.fullmatch(r"1-1-\d+", following):
                break
            if re.match(r"^序号\s", following) or following.startswith("合计"):
                break
            parts.append(following)
        return redact_private_text(_display_join(parts, limit * 2), limit), int(page)
    return "", 0


def _exact_basic_information_block(
    pages: list[PageLike],
    alias: str,
    *,
    max_lines: int = 55,
) -> list[tuple[int, str]]:
    flat: list[tuple[int, str]] = []
    for page in pages:
        flat.extend((int(page.number), line) for line in _page_lines(page))
    heading = re.compile(
        rf"^\s*(?:\d{{1,3}}|[一二三四五六七八九十]{{1,4}})[、.．]\s*{re.escape(alias)}\s*$"
    )
    for index, (_, line) in enumerate(flat):
        if not heading.match(line):
            continue
        block: list[tuple[int, str]] = []
        for item in flat[index + 1 : index + 1 + max_lines]:
            if block and _is_numbered_heading(item[1]):
                break
            block.append(item)
        if any(re.match(r"^名称\s*[：:]?\s*\S+", item[1]) for item in block):
            return block
    return []


def extract_basic_information(
    pages: list[PageLike],
    aliases: Iterable[str],
) -> dict[str, BasicInformation]:
    result: dict[str, BasicInformation] = {}
    for alias in aliases:
        block = _exact_basic_information_block(pages, alias)
        if not block:
            continue
        full_name, name_page = _field_value(block, ("名称",), 240)
        if not full_name:
            continue
        office_address, address_page = _field_value(
            block,
            ("住所", "注册地址", "主要经营场所", "办公地址", "联系地址"),
            240,
        )
        phone_text, phone_page = _field_value(block, ("联系电话", "电话"), 80)
        email_text, email_page = _field_value(block, ("电子邮箱", "邮箱"), 120)
        website_text, website_page = _field_value(block, ("互联网网址", "公司网址", "网站"), 200)
        phone_match = LANDLINE_PATTERN.search(phone_text)
        email_match = EMAIL_PATTERN.search(email_text)
        website_match = URL_PATTERN.search(website_text)
        phone = ""
        if phone_match and not MOBILE_PATTERN.search(phone_match.group(0)):
            phone = re.sub(r"\s+", "", phone_match.group(0)).replace("—", "-").replace("－", "-")
        email = email_match.group(0).lower() if email_match else ""
        website = website_match.group(0).rstrip(".,，。；;）)") if website_match else ""
        if website.startswith("www."):
            website = "https://" + website
        source_page = address_page or phone_page or email_page or website_page or name_page
        result[alias] = BasicInformation(
            disclosed_name=alias,
            full_name=full_name,
            page=source_page,
            office_address=office_address,
            phone=phone,
            email=email,
            website=website,
        )
    return result


def _institutional_name(alias: str, full_name: str, resolved: bool) -> bool:
    if not full_name or not _balanced_legal_name(full_name):
        return False
    if full_name in GENERIC_NAMES or alias in GENERIC_NAMES:
        return False
    if any(fragment in full_name or fragment in alias for fragment in NARRATIVE_NAME_FRAGMENTS):
        return False
    if any(
        marker in full_name
        for marker in (
            "成立时间",
            "成立日期",
            "统一社会信用代码",
            "注册号",
            "经营范围/主营业务",
            "经营范围",
        )
    ):
        return False
    if resolved and any(hint in full_name for hint in INSTITUTION_HINTS):
        return True
    if resolved and re.search(
        r"\b(?:capital|corporation|inc\.?|limited|ltd\.?|llc|fund|partners?)\b",
        full_name,
        flags=re.IGNORECASE,
    ):
        return True
    return any(hint in alias for hint in INSTITUTION_HINTS)


def classify_investor(name: str) -> str:
    if any(term in name for term in ("员工持股", "员工平台")):
        return "员工持股平台"
    if any(term in name for term in ("国资", "国有资本", "国投", "国新", "产业引导基金", "政府投资")):
        return "国资投资平台"
    if any(term in name for term in ("创业投资", "创投", "股权投资", "投资基金", "资本管理", "基金管理")):
        return "股权投资机构"
    if any(term in name for term in ("产业投资", "控股集团", "科技集团", "实业集团", "股份有限公司")):
        return "产业投资者"
    if "合伙企业" in name or "有限合伙" in name:
        return "投资合伙企业"
    return "其他机构股东"


def extract_institutional_investors(
    pages: list[PageLike],
    company_name: str,
    *,
    max_investors: int,
) -> list[dict[str, Any]]:
    shareholder_rows = parse_shareholder_rows(pages)
    aliases = [row.disclosed_name for row in shareholder_rows]
    definitions = extract_definition_map(pages, aliases)
    basic_information = extract_basic_information(pages, aliases)
    issuer_key = normalize_name(company_name)
    candidates: dict[str, dict[str, Any]] = {}

    for row in shareholder_rows:
        basic = basic_information.get(row.disclosed_name)
        definition = definitions.get(row.disclosed_name)
        full_name = clean_text(
            basic.full_name if basic else definition[0] if definition else row.disclosed_name,
            240,
        )
        resolution = "basic-information" if basic else "definitions" if definition else "table-only"
        full_key = normalize_name(full_name)
        if not full_key or full_key == issuer_key or issuer_key in full_key:
            continue
        if not _institutional_name(row.disclosed_name, full_name, resolution != "table-only"):
            continue

        item: dict[str, Any] = {
            "id": "star-investor-" + hashlib.sha256(full_key.encode("utf-8")).hexdigest()[:18],
            "name": full_name,
            "normalizedName": full_key,
            "institutional": True,
            "investorType": classify_investor(full_name),
            "sourcePage": row.page,
            "sourceSection": row.section,
            "evidence": row.evidence,
            "preIpoShares": round(row.pre_ipo_shares, 4),
            "preIpoOwnershipPct": round(row.pre_ipo_ownership_pct, 6),
            "nameResolution": resolution,
        }
        if normalize_name(row.disclosed_name) != full_key:
            item["disclosedName"] = row.disclosed_name
        if definition:
            item["definitionSourcePage"] = int(definition[1])
        if basic and any((basic.office_address, basic.phone, basic.email, basic.website)):
            contact = {
                key: value
                for key, value in {
                    "officeAddress": basic.office_address,
                    "phone": basic.phone,
                    "email": basic.email,
                    "website": basic.website,
                }.items()
                if value
            }
            contact["sourcePage"] = basic.page
            contact["scope"] = "招股说明书中该机构基本情况块披露的机构级联系方式"
            item["publicContact"] = contact
            item["contactStatus"] = "prospectus-public"
        else:
            item["contactStatus"] = "not-disclosed-in-prospectus"

        current = candidates.get(full_key)
        if current is None or float(item["preIpoOwnershipPct"]) > float(current["preIpoOwnershipPct"]):
            candidates[full_key] = item

    result = sorted(
        candidates.values(),
        key=lambda item: (
            -float(item["preIpoOwnershipPct"]),
            -float(item["preIpoShares"]),
            item["name"],
        ),
    )
    return result[: max(1, max_investors)]
