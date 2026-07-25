#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "tools" / "research_report_adapters.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"cannot find {label}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PATH.read_text(encoding="utf-8")
    text = replace_once(
        text,
        '''LANDING_TERMS = (
''',
        '''REJECT_TERMS = (
    "certificate",
    "certification",
    "privacy policy",
    "terms of use",
    "code of conduct",
    "supplier policy",
    "iso 9001",
    "press release pdf",
    "news release pdf",
    "proxy card",
    "form of proxy",
    "monthly return",
    "notice of meeting",
    "证书",
    "认证证书",
    "隐私政策",
    "使用条款",
    "月报表",
    "代表委任表格",
    "会议通知",
)
LANDING_TERMS = (
''',
        "reject terms",
    )
    text = replace_once(
        text,
        '''def is_relevant_text(text: str, company: dict[str, str]) -> bool:
    lowered = text.casefold()
    term_hit = any(term.casefold() in lowered for term in PDF_TERMS)
    alias_hit = any(alias.casefold() in lowered for alias in aliases(company))
    return term_hit and alias_hit
''',
        '''def is_rejected_text(text: str) -> bool:
    lowered = text.casefold()
    return any(term.casefold() in lowered for term in REJECT_TERMS)


def is_relevant_text(text: str, company: dict[str, str]) -> bool:
    lowered = text.casefold()
    if is_rejected_text(lowered):
        return False
    term_hit = any(term.casefold() in lowered for term in PDF_TERMS)
    alias_hit = any(alias.casefold() in lowered for alias in aliases(company))
    return term_hit and alias_hit
''',
        "relevant text filter",
    )
    text = replace_once(
        text,
        '''        combined = f"{anchor} {context} {url}"
        if not (
            is_relevant_text(combined, company)
            or (is_company_domain(url, website) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("hkexnews.hk" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("sec.gov" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
        ):
''',
        '''        combined = f"{anchor} {context} {url}"
        if is_rejected_text(combined) or not (
            is_relevant_text(combined, company)
            or (is_company_domain(url, website) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("hkexnews.hk" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
            or ("sec.gov" in host_name(url) and any(term in combined.casefold() for term in PDF_TERMS))
        ):
''',
        "anchor candidate filter",
    )
    text = replace_once(
        text,
        '''        context = strip_tags(escaped[max(0, window_at - 300): window_at + len(url) + 300])
        if not (
            is_relevant_text(context + " " + url, company)
            or is_company_domain(url, website)
            or "hkexnews.hk" in host_name(url)
            or "sec.gov" in host_name(url)
        ):
''',
        '''        context = strip_tags(escaped[max(0, window_at - 300): window_at + len(url) + 300])
        combined = context + " " + url
        if is_rejected_text(combined) or not (
            is_relevant_text(combined, company)
            or (
                (is_company_domain(url, website) or "hkexnews.hk" in host_name(url) or "sec.gov" in host_name(url))
                and any(term in combined.casefold() for term in PDF_TERMS)
            )
        ):
''',
        "raw PDF candidate filter",
    )
    PATH.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
