#!/usr/bin/env python3
"""Apply the research-report library integration to the listed-company detail page."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "app" / "ipo" / "[slug]" / "page.tsx"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        return text
    if old not in text:
        raise RuntimeError(f"cannot find {label}")
    return text.replace(old, new, 1)


def main() -> int:
    text = PAGE.read_text(encoding="utf-8")
    text = replace_once(
        text,
        'import type { Metadata } from "next";\nimport { notFound } from "next/navigation";',
        'import type { Metadata } from "next";\nimport Link from "next/link";\nimport { notFound } from "next/navigation";\nimport { ResearchReportLibrary } from "@/components/research-report-library";',
        "page imports",
    )
    text = replace_once(
        text,
        'import { ipoProfiles } from "@/lib/research-content";',
        'import { ipoProfiles } from "@/lib/research-content";\nimport { relatedResearchReports } from "@/lib/research-report-data";',
        "report data import",
    )
    text = replace_once(
        text,
        '  const marketCap = metricValue(marketData?.metrics, "marketCap");\n',
        '  const marketCap = metricValue(marketData?.metrics, "marketCap");\n  const relatedReports = relatedResearchReports({\n    companySlug: slug,\n    ticker: company.ticker,\n    sector: company.sector,\n    limit: 8,\n  });\n',
        "related report query",
    )

    old_section = '''          <Section id="研报与行业研究" title="研报与行业研究">
            <p className="research-directory-intro">
              使用公司名称“{displayName}”、代码“{company.ticker}”或行业“{marketData?.company.industry || company.sector}”检索。
              以下为第三方公开入口，部分全文可能需要登录或受平台权限限制。
            </p>
            <div className="research-directory-grid">
              <ResearchLink
                platform="萝卜投研"
                title="个股深度研究"
                description={`检索 ${displayName} 的券商观点、公司研究、财务预测与产业链信息。`}
                href="https://robo.datayes.com/"
              />
              <ResearchLink
                platform="萝卜投研"
                title="行业与产业链分析"
                description={`以“${marketData?.company.industry || company.sector}”为关键词查看行业数据和深度研究。`}
                href="https://robo.datayes.com/"
              />
              <ResearchLink
                platform="慧博投研"
                title="全市场券商研报"
                description="浏览券商公司调研、行业分析、投资策略、港美研究和新股研究。"
                href="https://p.hibor.com.cn/"
              />
              <ResearchLink
                platform="慧博投研"
                title="高级研报搜索"
                description={`在研究报告高级搜索中输入“${displayName}”或“${company.ticker}”。`}
                href="https://www.hibor.com.cn/supersearch.html"
              />
            </div>
          </Section>'''
    new_section = '''          <Section id="研报与行业研究" title="研报与行业研究">
            <p className="research-directory-intro">
              这里直接展示与“{displayName}”、代码“{company.ticker}”及行业“{marketData?.company.industry || company.sector}”相关的已归档 PDF。
              点击卡片进入站内阅读，不再跳转到第三方研报首页。
            </p>
            <ResearchReportLibrary reports={relatedReports} compact />
            <Link className="source-card" href="/reports">
              <span>06 / RESEARCH</span>
              <strong>查看全部公开研报 PDF</strong>
              <small>按公司、代码、机构和行业统一检索 →</small>
            </Link>
          </Section>'''
    text = replace_once(text, old_section, new_section, "research report section")

    text, count = re.subn(
        r'\nfunction ResearchLink\([\s\S]*?\n}\n\nfunction formatMetric',
        '\nfunction formatMetric',
        text,
        count=1,
    )
    if count == 0 and "function ResearchLink(" in text:
        raise RuntimeError("cannot remove obsolete ResearchLink helper")

    PAGE.write_text(text, encoding="utf-8")
    print("research report UI patch applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
