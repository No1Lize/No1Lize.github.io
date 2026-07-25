import type { IntelligenceEvent } from "@/lib/intelligence-data";
import type { SectorDefinition } from "@/lib/sector-definitions";
import type { TrackingTrack } from "@/lib/user-tracking";

const GENERIC_COMPANY_NAMES = new Set(["", "科技产业", "未分类"]);

const EVENT_GROUPS: Array<{ name: string; types: string[] }> = [
  { name: "科研与技术验证", types: ["技术突破", "论文"] },
  { name: "产品与系统工程", types: ["产品发布", "商业进展", "公司动态"] },
  { name: "融资与产业化", types: ["融资", "产业投资", "并购"] },
  { name: "政策与监管", types: ["政策", "监管文件"] },
  { name: "资本市场", types: ["IPO", "财报"] },
];

const FALLBACK_SUBSECTORS = [
  "基础研究",
  "关键技术与设备",
  "系统集成与工程验证",
  "商业化与监管",
];

function unique(values: Array<string | undefined>, limit = 12): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw?.replace(/\s+/g, " ").trim() ?? "";
    const key = value.toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function topCompanies(events: IntelligenceEvent[], region?: "中国" | "美国"): string[] {
  const counts = new Map<string, number>();
  for (const event of events) {
    if (region && event.region !== region) continue;
    const company = event.company?.trim() ?? "";
    if (GENERIC_COMPANY_NAMES.has(company)) continue;
    counts.set(company, (counts.get(company) ?? 0) + 1);
  }
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]))
    .slice(0, 3)
    .map(([company]) => company);
}

function eventGroups(events: IntelligenceEvent[]): string[] {
  return EVENT_GROUPS.filter((group) =>
    events.some((event) => group.types.includes(event.type)),
  ).map((group) => group.name);
}

function configuredFocus(track: TrackingTrack): string[] {
  return unique(
    [
      ...track.keywords,
      ...track.sampleCompanies,
      ...track.people,
    ],
    8,
  );
}

function buildDefinition(track: TrackingTrack, events: IntelligenceEvent[]): string {
  const keywords = unique(track.keywords, 4);
  const companies = unique(
    [...track.sampleCompanies, ...topCompanies(events)],
    4,
  );
  const focus = keywords.length
    ? `重点覆盖${keywords.join("、")}`
    : "覆盖基础研究、关键技术、工程验证与产业化进展";
  const actors = companies.length
    ? `，并跟踪${companies.join("、")}等样本主体`
    : "";
  return `${track.name}赛道${focus}${actors}。页面以技术里程碑、工程化能力、资本事件和政策监管为统一分析主线。`;
}

function buildSubsectors(track: TrackingTrack, events: IntelligenceEvent[]): string[] {
  const result = unique(
    [...track.keywords, ...eventGroups(events), ...FALLBACK_SUBSECTORS],
    8,
  );
  return result.length ? result : [track.name];
}

function buildChain(track: TrackingTrack, subsectors: string[]): SectorDefinition["chain"] {
  const technicalTerms = unique(subsectors.slice(0, 3), 3);
  const supplyTerms = technicalTerms.length
    ? technicalTerms.join("、")
    : `${track.name}关键技术`;
  return [
    {
      title: "基础研究",
      detail: `${track.name}核心原理、关键论文、实验指标与技术路线比较`,
    },
    {
      title: "关键技术与供应链",
      detail: `${supplyTerms}相关材料、设备、软件、核心部件与供应能力`,
    },
    {
      title: "系统集成与工程验证",
      detail: "系统性能、可靠性、成本、良率、建设进度与规模化验证",
    },
    {
      title: "商业部署与治理",
      detail: "示范项目、客户采用、融资、资本开支、政策许可与监管要求",
    },
  ];
}

function buildRegionLens(
  track: TrackingTrack,
  events: IntelligenceEvent[],
  region: "中国" | "美国",
): string {
  const regionalEvents = events.filter((event) => event.region === region);
  const companies = topCompanies(events, region);
  const companyText = companies.length
    ? `，重点样本包括${companies.join("、")}`
    : "";
  if (region === "中国") {
    return `关注中国市场中的${track.name}科研平台、关键供应链、工程化速度、政策支持与示范项目。当前快照收录 ${regionalEvents.length} 项相关事件${companyText}。`;
  }
  return `关注美国市场中的${track.name}前沿路线、创业公司、资本投入、工程节点与规模化部署。当前快照收录 ${regionalEvents.length} 项相关事件${companyText}。`;
}

function buildResearchFocus(
  track: TrackingTrack,
  events: IntelligenceEvent[],
): string[] {
  const types = new Set(events.map((event) => event.type));
  const result: string[] = [];

  for (const keyword of unique(track.keywords, 2)) {
    result.push(`${keyword}的技术进展与产业影响`);
  }
  result.push(`${track.name}核心性能指标与技术里程碑`);
  result.push("工程化成本、可靠性与规模化能力");
  if (["融资", "产业投资", "并购", "IPO"].some((type) => types.has(type))) {
    result.push("融资节奏、资本开支与项目兑现");
  }
  if (["政策", "监管文件"].some((type) => types.has(type))) {
    result.push("政策、监管、安全边界与许可进度");
  }
  if (track.sampleCompanies.length || topCompanies(events).length) {
    result.push("样本公司工程节点与商业化进度");
  }
  if (track.people.length) {
    result.push("关键人物观点与研究路线变化");
  }
  return unique(result, 6);
}

function buildRisks(track: TrackingTrack, events: IntelligenceEvent[]): string[] {
  const sources = new Set(events.map((event) => event.source.url)).size;
  const risks = [
    `${track.name}技术路线与核心指标尚未充分收敛`,
    "从实验或原型到规模部署的工程化周期可能显著延长",
    "资本开支、融资续航与项目延期风险",
    "关键设备、材料、人才、供应链与监管约束",
  ];
  if (!events.length) {
    risks.push("当前公开事件较少，热度与趋势判断存在样本不足风险");
  } else if (sources < 2) {
    risks.push("公开信息来源较集中，重要结论需要更多独立信源交叉验证");
  }
  return unique(risks, 5);
}

export function generateSectorDefinition(
  track: TrackingTrack,
  events: IntelligenceEvent[],
): SectorDefinition {
  const subsectors = buildSubsectors(track, events);
  return {
    slug: track.slug,
    name: track.name,
    definition: buildDefinition(track, events),
    subsectors,
    chain: buildChain(track, subsectors),
    chinaLens: buildRegionLens(track, events, "中国"),
    usLens: buildRegionLens(track, events, "美国"),
    researchFocus: buildResearchFocus(track, events),
    risks: buildRisks(track, events),
  };
}

export function resolveSectorDefinition(
  track: TrackingTrack,
  events: IntelligenceEvent[],
  curated?: SectorDefinition,
): SectorDefinition {
  const generated = generateSectorDefinition(track, events);
  if (!curated) return generated;

  return {
    slug: track.slug,
    name: track.name,
    definition: curated.definition || generated.definition,
    subsectors: unique(
      [...track.keywords, ...curated.subsectors, ...generated.subsectors],
      8,
    ),
    chain: curated.chain.length ? curated.chain : generated.chain,
    chinaLens: curated.chinaLens || generated.chinaLens,
    usLens: curated.usLens || generated.usLens,
    researchFocus: unique(
      [...track.keywords, ...curated.researchFocus, ...generated.researchFocus],
      6,
    ),
    risks: unique([...curated.risks, ...generated.risks], 6),
  };
}

export function sectorCompleteness(
  track: TrackingTrack,
  events: IntelligenceEvent[],
  curated = false,
): number {
  const sourceCount = new Set(events.map((event) => event.source.url)).size;
  const score =
    10 +
    Math.min(track.keywords.length, 5) * 3 +
    Math.min(track.sampleCompanies.length, 5) * 3 +
    Math.min(track.people.length, 4) * 2 +
    (events.length ? 20 : 0) +
    Math.min(events.length, 10) * 2 +
    Math.min(sourceCount, 5) * 3 +
    (curated ? 12 : 0);
  return Math.min(100, score);
}

export function trackSearchSeed(track: TrackingTrack): string[] {
  return unique([track.name, ...configuredFocus(track)], 16);
}
