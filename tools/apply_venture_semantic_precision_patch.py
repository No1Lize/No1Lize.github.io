#!/usr/bin/env python3
from pathlib import Path

path = Path("tools/venture_profile_extraction.py")
text = path.read_text(encoding="utf-8")

noise_old = '''    "研究院",
}

GENERIC_PRODUCT_LABELS = {
'''
noise_new = '''    "研究院",
    "高级",
    "高级副",
    "副总",
    "总裁办",
}

GENERIC_PRODUCT_LABELS = {
'''
if noise_new not in text:
    if noise_old not in text:
        raise SystemExit("person noise marker not found")
    text = text.replace(noise_old, noise_new, 1)

doc_block = '''PRODUCT_DOCUMENT_TERMS = (
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
event_block = doc_block + '''PRODUCT_EVENT_TERMS = (
    "competition",
    "contest",
    "event",
    "conference",
    "webinar",
    "news",
    "blog",
    "大赛",
    "赛事",
    "活动",
    "大会",
    "发布会",
    "新闻",
    "报告",
)

'''
if "PRODUCT_EVENT_TERMS = (" not in text:
    if doc_block not in text:
        raise SystemExit("product document block not found")
    text = text.replace(doc_block, event_block, 1)

specific_start = text.index("def _specific_product_label(value: str) -> bool:\n")
specific_end = text.index("\n\ndef sanitize_product_items", specific_start)
specific_new = '''def _specific_product_label(value: str) -> bool:
    item = clean_text(value, 220).strip(" >›→-|｜")
    lowered = item.casefold()
    compact = re.sub(r"[^a-z0-9\\u3400-\\u9fff]+", "", lowered)
    if not item or len(item) < 3 or len(item) > 180:
        return False
    if lowered in NAVIGATION_NOISE or lowered in GENERIC_PRODUCT_LABELS:
        return False
    if any(term in lowered for term in (*PRODUCT_DOCUMENT_TERMS, *PRODUCT_EVENT_TERMS)):
        return False
    if compact in {re.sub(r"\\W+", "", value).casefold() for value in GENERIC_PRODUCT_LABELS}:
        return False
    chinese_product = bool(
        re.search(
            r"[\\u3400-\\u9fffA-Za-z0-9.+_-]{2,}(?:机器人|模型|平台|系统|芯片|引擎|终端|助手|智能体|API)(?:[A-Za-z0-9.+_-]*)?$",
            item,
            re.IGNORECASE,
        )
    )
    english_product = bool(
        re.search(r"\\b[A-Za-z][A-Za-z.+_-]*\\d+[A-Za-z0-9.+_-]*\\b", item)
        or re.search(
            r"\\b[A-Z][A-Za-z0-9.+_-]*(?:\\s+[A-Z][A-Za-z0-9.+_-]*){0,3}\\s+(?:Platform|Model|Robot|System|API|Agent|Chip|Engine)\\b",
            item,
        )
    )
    return chinese_product or english_product
'''
text = text[:specific_start] + specific_new + text[specific_end:]

old_sanitize_condition = '''        if any(term in lowered for term in PRODUCT_DOCUMENT_TERMS):
            continue
'''
new_sanitize_condition = '''        if any(term in lowered for term in (*PRODUCT_DOCUMENT_TERMS, *PRODUCT_EVENT_TERMS)):
            continue
'''
if new_sanitize_condition not in text:
    if old_sanitize_condition not in text:
        raise SystemExit("retained product sanitizer marker not found")
    text = text.replace(old_sanitize_condition, new_sanitize_condition, 1)

old_alias = '''        if any(alias in name.casefold() for alias in alias_keys if len(alias) >= 2):
            continue
'''
new_alias = '''        lowered_name = name.casefold()
        if any(
            alias in lowered_name or lowered_name in alias
            for alias in alias_keys
            if len(alias) >= 2
        ):
            continue
'''
count = text.count(old_alias)
if count:
    text = text.replace(old_alias, new_alias)
elif text.count(new_alias) < 2:
    raise SystemExit(f"team alias markers missing: old={count}, new={text.count(new_alias)}")

path.write_text(text, encoding="utf-8")
print("venture semantic precision rules applied")
