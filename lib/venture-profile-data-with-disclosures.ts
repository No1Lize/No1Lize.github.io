export * from "./venture-profile-data";

import {
  getCompanyVentureProfile as getBaseCompanyVentureProfile,
  ventureProfileGeneratedAt,
  type CompanyVentureProfile,
  type VentureCapitalEvent,
  type VentureCapitalSummary,
  type VentureSource,
} from "./venture-profile-data";
import {
  getListedCompanyDisclosure,
  listedDisclosureGeneratedAt,
} from "./listed-company-disclosure-data";

function uniqueBy<T>(values: T[], key: (value: T) => string) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const identity = key(value);
    if (!identity || seen.has(identity)) return false;
    seen.add(identity);
    return true;
  });
}

function disclosureEvents(slug: string): VentureCapitalEvent[] {
  const disclosure = getListedCompanyDisclosure(slug);
  return (disclosure?.events ?? []).map((event) => ({
    date: event.publishedAt,
    type: event.documentType,
    title: event.title,
    summary: `${event.exchange} · ${event.source.name}。${event.summary}`,
    sourceUrl: event.source.url,
  }));
}

function disclosureSources(slug: string): VentureSource[] {
  const disclosure = getListedCompanyDisclosure(slug);
  return (disclosure?.events ?? []).map((event) => ({
    name: event.source.name,
    url: event.source.url,
    level: event.source.level,
    section: event.documentType,
    title: event.title,
    publishedAt: event.publishedAt,
  }));
}

function disclosureSummary(slug: string): VentureCapitalSummary | undefined {
  const disclosure = getListedCompanyDisclosure(slug);
  if (!disclosure?.events.length) return undefined;
  const types = Array.from(
    new Set(disclosure.events.map((event) => event.documentType)),
  );
  const sourceNames = Array.from(
    new Set(disclosure.events.map((event) => event.source.name)),
  );
  return {
    eventCount: disclosure.events.length,
    disclosedAmounts: [],
    rounds: types,
    majorInvestors: [],
    latestDate: disclosure.events[0]?.publishedAt,
    latestRound: disclosure.events[0]?.documentType,
    summary: `已从${sourceNames.join("、")}识别 ${disclosure.events.length} 份可核对的上市公司披露文件，其中官方交易所或指定披露平台文件 ${disclosure.officialEventCount} 份。金额、投资方等字段仅在原文件明确披露时记录，不作推测。`,
  };
}

export function getCompanyVentureProfile(
  slug: string,
): CompanyVentureProfile | undefined {
  const base = getBaseCompanyVentureProfile(slug);
  const disclosure = getListedCompanyDisclosure(slug);
  if (!disclosure?.events.length) return base;

  const capitalMarkets = uniqueBy(
    [...disclosureEvents(slug), ...(base?.capitalMarkets ?? [])].sort((a, b) =>
      (b.date || "").localeCompare(a.date || ""),
    ),
    (event) => event.sourceUrl || `${event.date ?? ""}-${event.title}`,
  ).slice(0, 30);
  const sources = uniqueBy(
    [...disclosureSources(slug), ...(base?.sources ?? [])],
    (source) => source.url,
  ).slice(0, 40);
  const updatedAt = [
    disclosure.updatedAt,
    listedDisclosureGeneratedAt,
    base?.updatedAt,
    ventureProfileGeneratedAt,
  ]
    .filter(Boolean)
    .sort()
    .at(-1) || "";

  if (base) {
    return {
      ...base,
      updatedAt,
      status: base.status === "fallback" ? "partial" : base.status,
      capitalSummary: base.capitalSummary ?? disclosureSummary(slug),
      capitalMarkets,
      sources,
      warnings: uniqueBy(
        [
          ...(base.warnings ?? []),
          disclosure.fallbackEventCount
            ? `${disclosure.fallbackEventCount} 份文件来自东方财富公告数据库兜底，已保留来源层级标记。`
            : "",
        ].filter(Boolean),
        (warning) => warning,
      ),
    };
  }

  return {
    slug,
    name: disclosure.name,
    updatedAt,
    status: "partial",
    background: "公司基础资料来自公开公司目录，资本市场信息来自交易所及指定信息披露平台。",
    technology: "技术与产品信息等待公司官网档案刷新补充。",
    products: [],
    team: [],
    financing: [],
    capitalSummary: disclosureSummary(slug),
    capitalMarkets,
    sources,
    warnings: disclosure.fallbackEventCount
      ? [`${disclosure.fallbackEventCount} 份文件来自东方财富公告数据库兜底。`]
      : [],
  };
}
