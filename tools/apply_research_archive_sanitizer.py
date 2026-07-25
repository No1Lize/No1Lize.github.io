#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "tools" / "research_report_adapters.py"
CRAWLER = ROOT / "tools" / "crawl_research_reports.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"cannot find {label}")
    return text.replace(old, new, 1)


def patch_adapter() -> None:
    text = ADAPTER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''    "notice of meeting",
    "证书",
''',
        '''    "notice of meeting",
    "annual general meeting",
    "poll results",
    "form of proxy",
    "monthly return",
    "next day disclosure return",
    "board meeting",
    "notice of agm",
    "results of agm",
    "证书",
''',
        "English governance reject terms",
    )
    text = replace_once(
        text,
        '''    "会议通知",
)
''',
        '''    "会议通知",
    "股东大会通知",
    "股东大会表决结果",
    "委任表格",
    "代表委任表格",
    "月报表",
    "翌日披露报表",
    "董事会会议日期",
)
''',
        "Chinese governance reject terms",
    )
    ADAPTER.write_text(text, encoding="utf-8")


def patch_crawler() -> None:
    text = CRAWLER.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''        discover_web_candidates,
        load_sec_ticker_map,
''',
        '''        discover_web_candidates,
        is_rejected_text,
        load_sec_ticker_map,
''',
        "package rejected-text import",
    )
    # Replace the second occurrence in the fallback import as well.
    marker = '''    from research_report_adapters import (
        discover_sec_candidates,
        discover_web_candidates,
        load_sec_ticker_map,
'''
    replacement = '''    from research_report_adapters import (
        discover_sec_candidates,
        discover_web_candidates,
        is_rejected_text,
        load_sec_ticker_map,
'''
    text = replace_once(text, marker, replacement, "direct rejected-text import")
    text = replace_once(
        text,
        '''def crawl_company(
''',
        '''def report_is_relevant(report: dict[str, Any]) -> bool:
    text = " ".join(
        str(report.get(key) or "")
        for key in ("title", "summary", "sourcePageUrl", "originalPdfUrl")
    )
    return not is_rejected_text(text)


def crawl_company(
''',
        "retained report relevance helper",
    )
    text = replace_once(
        text,
        '''    for report in [*new_reports, *previous_reports]:
        report_id = clean_text(report.get("id"), 160)
''',
        '''    for report in [*new_reports, *previous_reports]:
        if not report_is_relevant(report):
            continue
        report_id = clean_text(report.get("id"), 160)
''',
        "retained report filter",
    )
    CRAWLER.write_text(text, encoding="utf-8")


def main() -> int:
    patch_adapter()
    patch_crawler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
