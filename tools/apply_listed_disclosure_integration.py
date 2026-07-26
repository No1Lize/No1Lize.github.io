#!/usr/bin/env python3
"""Apply the listed-disclosure integration as one atomic repository patch."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "app" / "companies" / "[slug]" / "page.tsx"
CRAWLER = ROOT / "tools" / "crawl_listed_company_disclosures.py"
WORKFLOW = ROOT / ".github" / "workflows" / "scheduled-sync.yml"


def replace_once(body: str, old: str, new: str, label: str) -> str:
    if old not in body:
        raise RuntimeError(f"patch target not found: {label}")
    if body.count(old) != 1:
        raise RuntimeError(f"patch target is not unique: {label}")
    return body.replace(old, new, 1)


def patch_crawler() -> None:
    body = CRAWLER.read_text(encoding="utf-8")
    body = replace_once(
        body,
        '    for company in comparable_previous.get("companies", {}).values() if isinstance(comparable_previous.get("companies"), dict) else []:\n',
        '    previous_companies = comparable_previous.get("companies", {})\n'
        '    for company in (\n'
        '        previous_companies.values() if isinstance(previous_companies, dict) else []\n'
        '    ):\n',
        "previous company timestamp normalization",
    )
    body = replace_once(
        body,
        '    for company in comparable_next.get("companies", {}).values() if isinstance(comparable_next.get("companies"), dict) else []:\n',
        '    next_companies = comparable_next.get("companies", {})\n'
        '    for company in (\n'
        '        next_companies.values() if isinstance(next_companies, dict) else []\n'
        '    ):\n',
        "next company timestamp normalization",
    )
    CRAWLER.write_text(body, encoding="utf-8")


def patch_page() -> None:
    body = PAGE.read_text(encoding="utf-8")
    body = replace_once(
        body,
        '} from "@/lib/venture-profile-data";\n',
        '} from "@/lib/venture-profile-data";\n'
        'import { getListedCompanyDisclosure } from "@/lib/listed-company-disclosure-data";\n',
        "listed disclosure import",
    )

    pattern = re.compile(
        r"  const research = getCompanyResearch\(company\);\n"
        r"  const venture = getCompanyVentureProfile\(slug\);\n"
        r"  const updateDate =[\s\S]*?"
        r"  const exitPerformance = venture\?\.exitPerformance;\n"
    )
    replacement = '''  const research = getCompanyResearch(company);
  const venture = getCompanyVentureProfile(slug);
  const disclosure = getListedCompanyDisclosure(slug);
  const updateDate = latestDate([
    disclosure?.updatedAt?.slice(0, 10),
    venture?.updatedAt?.slice(0, 10),
    ventureProfileGeneratedAt?.slice(0, 10),
    snapshotDate,
  ]);
  const background = venture?.projectBackground?.summary || venture?.background || company.summary;
  const projectBackground = venture?.projectBackground;
  const technology = venture?.researchTechnology || venture?.technology || research.technology;
  const products = venture?.products?.length
    ? venture.products
    : [company.product];
  const technologyProducts = venture?.technologyProducts ?? [];
  const team = venture?.team ?? [];
  const financing = venture?.financing ?? [];
  const disclosureCapitalEvents: VentureCapitalEvent[] = (disclosure?.events ?? []).map(
    (event) => ({
      date: event.publishedAt,
      type: event.documentType,
      title: event.title,
      summary: `${event.exchange} · ${event.source.name}。${event.summary}`,
      sourceUrl: event.source.url,
    }),
  );
  const capitalMarkets = uniqueCapitalEvents([
    ...(venture?.capitalMarkets ?? []),
    ...disclosureCapitalEvents,
  ]).slice(0, 30);
  const disclosureCapitalSummary = disclosure?.events.length
    ? {
        eventCount: disclosure.events.length,
        disclosedAmounts: [],
        rounds: Array.from(
          new Set(disclosure.events.map((event) => event.documentType)),
        ),
        majorInvestors: [],
        latestDate: disclosure.events[0]?.publishedAt,
        latestRound: disclosure.events[0]?.documentType,
        summary: `已从${Array.from(
          new Set(disclosure.events.map((event) => event.source.name)),
        ).join("、")}识别 ${disclosure.events.length} 份上市公司披露文件，其中官方交易所或指定披露平台文件 ${disclosure.officialEventCount} 份。`,
      }
    : undefined;
  const capitalSummary = venture?.capitalSummary ?? disclosureCapitalSummary;
  const exitPerformance = venture?.exitPerformance;
'''
    body, count = pattern.subn(replacement, body, count=1)
    if count != 1:
        raise RuntimeError("company detail data block patch failed")

    body = replace_once(
        body,
        '    ...events.slice(0, 6).map((event) => ({\n'
        '      name: event.source.name,\n'
        '      url: event.source.url,\n'
        '      level: event.source.level,\n'
        '      section: event.type,\n'
        '      title: event.title,\n'
        '      publishedAt: event.publishedAt,\n'
        '    })),\n',
        '    ...events.slice(0, 6).map((event) => ({\n'
        '      name: event.source.name,\n'
        '      url: event.source.url,\n'
        '      level: event.source.level,\n'
        '      section: event.type,\n'
        '      title: event.title,\n'
        '      publishedAt: event.publishedAt,\n'
        '    })),\n'
        '    ...(disclosure?.events ?? []).slice(0, 12).map((event) => ({\n'
        '      name: event.source.name,\n'
        '      url: event.source.url,\n'
        '      level: event.source.level,\n'
        '      section: event.documentType,\n'
        '      title: event.title,\n'
        '      publishedAt: event.publishedAt,\n'
        '    })),\n',
        "disclosure evidence sources",
    )

    body = replace_once(
        body,
        '            {venture && <span>证据完整度 {venture.evidenceScore ?? 0}%</span>}\n',
        '            {venture && <span>证据完整度 {venture.evidenceScore ?? 0}%</span>}\n'
        '            {disclosure?.listings.map((listing) => (\n'
        '              <span key={`${listing.market}-${listing.ticker}`}>\n'
        '                {listing.market} {listing.ticker}\n'
        '              </span>\n'
        '            ))}\n'
        '            {disclosure?.events.length ? (\n'
        '              <span>监管披露 {disclosure.events.length} 条</span>\n'
        '            ) : null}\n',
        "listing chips",
    )

    body = replace_once(
        body,
        '                <Insight label="融资证据汇总" text={capitalSummary.summary} />\n',
        '                <Insight\n'
        '                  label={venture?.capitalSummary ? "融资证据汇总" : "监管披露汇总"}\n'
        '                  text={capitalSummary.summary}\n'
        '                />\n',
        "capital summary label",
    )
    body = replace_once(
        body,
        '                  label="融资阶段"\n',
        '                  label={venture?.capitalSummary ? "融资阶段" : "监管文件类型"}\n',
        "capital type label",
    )
    body = replace_once(
        body,
        '                  ? "目录显示公司已上市，但本轮尚未识别到更细的上市、并购或退出证据；后续将连接交易所和监管披露补齐。"\n',
        '                  ? "本轮尚未从交易所、指定披露平台或公告数据库识别到可核对的资本市场文件。"\n',
        "listed empty state",
    )
    body = replace_once(
        body,
        '            <strong>{financing.length + capitalMarkets.length}</strong>\n',
        '            <strong>{financing.length + capitalMarkets.length}</strong>\n',
        "capital event count anchor",
    )

    helper_anchor = 'function uniqueSources(sources: VentureSource[]) {\n'
    helpers = '''function latestDate(values: (string | undefined)[]) {
  return values.filter((value): value is string => Boolean(value)).sort().at(-1) || "";
}

function uniqueCapitalEvents(items: VentureCapitalEvent[]) {
  const seen = new Set<string>();
  return [...items]
    .sort((a, b) => (b.date || "").localeCompare(a.date || ""))
    .filter((item) => {
      const key = item.sourceUrl || `${item.date ?? ""}-${item.title}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

'''
    body = replace_once(body, helper_anchor, helpers + helper_anchor, "capital helpers")
    PAGE.write_text(body, encoding="utf-8")


def patch_workflow() -> None:
    body = WORKFLOW.read_text(encoding="utf-8")
    body = replace_once(
        body,
        '      - tools/crawl_articles.py\n',
        '      - tools/crawl_articles.py\n'
        '      - tools/crawl_listed_company_disclosures.py\n',
        "crawler workflow trigger",
    )
    body = replace_once(
        body,
        '      - config/intelligence_sources.json\n',
        '      - config/intelligence_sources.json\n'
        '      - config/listed_company_disclosure_sources.json\n',
        "disclosure config trigger",
    )
    body = replace_once(
        body,
        '      - name: Crawl all fixed and user-configured official company sources\n',
        '      - name: Crawl official exchange and designated disclosure sources\n'
        '        run: python tools/crawl_listed_company_disclosures.py\n'
        '      - name: Crawl all fixed and user-configured official company sources\n',
        "official disclosure crawl step",
    )
    body = replace_once(
        body,
        '      - name: Validate data quality\n',
        '      - name: Validate listed-company disclosure snapshot\n'
        '        run: python tools/crawl_listed_company_disclosures.py --validate-only\n'
        '      - name: Validate data quality\n',
        "disclosure validation step",
    )
    body = replace_once(
        body,
        '          if git diff --quiet -- public/data/articles.json public/data/market_profiles.json public/data/people.json; then\n',
        '          if git diff --quiet -- public/data/articles.json public/data/listed_company_disclosures.json public/data/market_profiles.json public/data/people.json; then\n',
        "disclosure data diff",
    )
    body = replace_once(
        body,
        '          git add public/data/articles.json public/data/market_profiles.json public/data/people.json\n',
        '          git add public/data/articles.json public/data/listed_company_disclosures.json public/data/market_profiles.json public/data/people.json\n',
        "first disclosure data add",
    )
    body = replace_once(
        body,
        '            python tools/crawl_articles.py --validate-only\n',
        '            python tools/crawl_listed_company_disclosures.py --validate-only\n'
        '            python tools/crawl_articles.py --validate-only\n',
        "rebase disclosure validation",
    )
    body = replace_once(
        body,
        '            git add public/data/articles.json public/data/market_profiles.json public/data/people.json\n',
        '            git add public/data/articles.json public/data/listed_company_disclosures.json public/data/market_profiles.json public/data/people.json\n',
        "second disclosure data add",
    )
    WORKFLOW.write_text(body, encoding="utf-8")


def main() -> int:
    patch_crawler()
    patch_page()
    patch_workflow()
    print("Applied listed-company disclosure integration.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
