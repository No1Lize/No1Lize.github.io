#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/venture_profile_extraction.py")
text = path.read_text(encoding="utf-8")

noise_marker = '''NAVIGATION_NOISE = {
'''
company_marker = '''COMPANY_LINK_TERMS = {
'''
noise_block = '''PERSON_NAME_NOISE = {
    "关于",
    "新闻",
    "资讯",
    "生产力",
    "营销",
    "联席",
    "产品",
    "技术",
    "公司",
    "集团",
    "智能",
    "解决方案",
    "业务",
    "研发",
    "服务",
    "平台",
    "团队",
    "我们",
    "更多",
    "联系",
    "加入",
    "招聘",
    "官网",
    "中心",
    "部门",
    "事业部",
    "办公室",
    "委员会",
    "研究院",
}

GENERIC_PRODUCT_LABELS = {
    "product",
    "products",
    "product overview",
    "our products",
    "产品",
    "产品中心",
    "产品概览",
    "产品软件包",
    "产品参数",
    "产品手册",
    "产品资料",
    "产品资料与下载",
    "产品用户手册",
    "数据服务",
    "解决方案",
    "服务",
    "售后服务政策",
}

PRODUCT_DOCUMENT_TERMS = (
    "manual",
    "documentation",
    "docs",
    "download",
    "support",
    "policy",
    "specification",
    "用户手册",
    "产品手册",
    "产品资料",
    "资料下载",
    "下载",
    "售后",
    "参数",
    "软件包",
)

'''
if noise_block not in text:
    if company_marker not in text:
        raise SystemExit("company marker not found")
    text = text.replace(company_marker, noise_block + company_marker, 1)

old_products = '''def extract_products(pages: Sequence[ParsedPage], fallback: str) -> list[str]:
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
    for item in re.split(r"[、，,;/]|\\s+与\\s+|\\s+and\\s+", clean_text(fallback, 600), flags=re.IGNORECASE):
        item = clean_text(item, 180)
        if item:
            candidates.append((1, item))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    result: list[str] = []
    seen: set[str] = set()
    for _, item in candidates:
        key = re.sub(r"\\W+", "", item).casefold()
        if not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= 10:
            break
    return result
'''
new_products = '''def _specific_product_label(value: str) -> bool:
    item = clean_text(value, 220).strip(" >›→-|｜")
    lowered = item.casefold()
    compact = re.sub(r"[^a-z0-9\\u3400-\\u9fff]+", "", lowered)
    if not item or len(item) < 3 or len(item) > 180:
        return False
    if lowered in NAVIGATION_NOISE or lowered in GENERIC_PRODUCT_LABELS:
        return False
    if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):
        return False
    if compact in {re.sub(r"\\W+", "", value).casefold() for value in GENERIC_PRODUCT_LABELS}:
        return False
    return bool(
        re.search(r"[A-Z0-9][A-Za-z0-9.+_-]*", item)
        or re.search(r"[\\u3400-\\u9fff]{2,}(?:机器人|模型|平台|系统|芯片|引擎|终端|助手|智能体|API)", item, re.IGNORECASE)
    )


def extract_products(pages: Sequence[ParsedPage], fallback: str) -> list[str]:
    candidates: list[tuple[int, str]] = []
    # The catalog product description is manually curated and therefore outranks
    # discovered navigation labels. Web discovery only adds concrete model names.
    for item in re.split(r"[、，,;/]|\\s+与\\s+|\\s+and\\s+", clean_text(fallback, 600), flags=re.IGNORECASE):
        item = clean_text(item, 180).strip(" >›→-|｜")
        if item:
            candidates.append((5, item))
    for page in pages:
        for value in [page.title, *page.headings, *(text for _, text in page.links)]:
            item = clean_text(value, 220).strip(" >›→-|｜")
            if not _specific_product_label(item):
                continue
            lowered = item.casefold()
            score = 2 + sum(
                2 for keyword in PRODUCT_KEYWORDS if keyword.casefold() in lowered
            )
            candidates.append((score, item))
    candidates.sort(key=lambda item: (-item[0], len(item[1]), item[1]))
    result: list[str] = []
    seen: set[str] = set()
    for _, item in candidates:
        key = re.sub(r"\\W+", "", item).casefold()
        if not key or key in seen:
            continue
        result.append(item)
        seen.add(key)
        if len(result) >= 10:
            break
    return result
'''
if new_products not in text:
    if old_products not in text:
        raise SystemExit("product extractor marker not found")
    text = text.replace(old_products, new_products, 1)

old_person = '''def _valid_person_name(name: str) -> bool:
    compact = clean_text(name, 120)
    if not compact or len(compact) < 2 or len(compact) > 80:
        return False
    if compact.casefold() in NAVIGATION_NOISE:
        return False
    if re.search(r"\\d|https?://|@", compact):
        return False
    return bool(re.search(r"[A-Za-z\\u3400-\\u9fff]", compact))
'''
new_person = '''def _valid_person_name(name: str) -> bool:
    compact = clean_text(name, 120).strip(" ,，:：;；-|｜")
    lowered = compact.casefold()
    if not compact or len(compact) < 2 or len(compact) > 80:
        return False
    if lowered in NAVIGATION_NOISE:
        return False
    if re.search(r"\\d|https?://|@", compact):
        return False
    if re.fullmatch(r"[\\u3400-\\u9fff·]{2,6}", compact):
        return not any(noise in compact for noise in PERSON_NAME_NOISE)
    return bool(
        re.fullmatch(
            r"[A-Z][A-Za-z'.-]+(?:\\s+[A-Z][A-Za-z'.-]+){1,3}",
            compact,
        )
    )
'''
if new_person not in text:
    if old_person not in text:
        raise SystemExit("person validator marker not found")
    text = text.replace(old_person, new_person, 1)

old_alias = '''        if not _valid_person_name(name) or name.casefold() in alias_keys:
            continue
'''
new_alias = '''        if not _valid_person_name(name):
            continue
        if any(alias in name.casefold() for alias in alias_keys if len(alias) >= 2):
            continue
'''
if new_alias not in text:
    if old_alias not in text:
        raise SystemExit("alias filter marker not found")
    text = text.replace(old_alias, new_alias, 1)

path.write_text(text, encoding="utf-8")
print("venture semantic filters applied")
