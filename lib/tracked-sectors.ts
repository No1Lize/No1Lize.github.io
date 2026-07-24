import {
  intelligenceEvents,
  sectors as baseSectors,
  type IntelligenceEvent,
  type Sector,
} from "@/lib/intelligence-data";
import {
  userTrackingConfig,
  type TrackingTrack,
} from "@/lib/user-tracking";

export type TrackedSector = Sector & {
  tracking: TrackingTrack;
  aliases: string[];
  baseName?: string;
};

type SectorRaw = {
  tracking: TrackingTrack;
  base?: Sector;
  aliases: string[];
  events: IntelligenceEvent[];
  financing: number;
  institutions: number;
  weightedEvents: number;
  ipo: number;
  research: number;
  current: number;
  previous: number;
};

function unique(values: string[], limit = 12): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const value of values) {
    const cleaned = value.trim();
    const key = cleaned.toLowerCase();
    if (!cleaned || seen.has(key)) continue;
    result.push(cleaned);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function dateValue(value: string): number {
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function normalizer(values: number[]): (value: number) => number {
  const maximum = Math.max(...values, 0);
  return (value) => (maximum > 0 ? Math.round((value / maximum) * 100) : 0);
}

function genericDefinition(track: TrackingTrack): string {
  const focus = unique([
    ...track.keywords,
    ...track.sampleCompanies,
    ...track.people,
  ], 6);
  return focus.length
    ? `聚焦${focus.join("、")}等方向，持续跟踪技术里程碑、公司进展、资本事件与关键人物动向。`
    : `持续跟踪${track.name}相关技术、公司、资本事件与产业化进展。`;
}

function buildRaw(): SectorRaw[] {
  const baseBySlug = new Map(baseSectors.map((sector) => [sector.slug, sector]));
  const baseByName = new Map(baseSectors.map((sector) => [sector.name, sector]));
  const asOf = Math.max(
    Date.now(),
    ...intelligenceEvents.map((event) => dateValue(event.publishedAt)),
  );
  const yearAgo = asOf - 365 * 24 * 60 * 60 * 1000;
  const ninetyDaysAgo = asOf - 90 * 24 * 60 * 60 * 1000;
  const previousNinetyDays = asOf - 180 * 24 * 60 * 60 * 1000;

  return userTrackingConfig.tracks
    .filter((track) => track.enabled)
    .map((tracking) => {
      const base = baseBySlug.get(tracking.slug) ?? baseByName.get(tracking.name);
      const aliases = unique([tracking.name, base?.name ?? ""], 4);
      const events = intelligenceEvents.filter(
        (event) =>
          aliases.includes(event.sector) && dateValue(event.publishedAt) >= yearAgo,
      );
      const financing = events.filter((event) => event.type === "融资").length;
      const institutions = new Set(
        events.flatMap((event) => event.institutions ?? []),
      ).size;
      const weightedEvents = Math.round(
        events.reduce((sum, event) => sum + event.importance, 0) / 100,
      );
      const ipo = events.filter((event) =>
        ["IPO", "监管文件", "财报"].includes(event.type),
      ).length;
      const research = events.filter((event) =>
        ["技术突破", "政策", "产品发布", "论文"].includes(event.type),
      ).length;
      const current = events.filter(
        (event) => dateValue(event.publishedAt) >= ninetyDaysAgo,
      ).length;
      const previous = events.filter((event) => {
        const timestamp = dateValue(event.publishedAt);
        return timestamp >= previousNinetyDays && timestamp < ninetyDaysAgo;
      }).length;
      return {
        tracking,
        base,
        aliases,
        events,
        financing,
        institutions,
        weightedEvents,
        ipo,
        research,
        current,
        previous,
      };
    });
}

function buildTrackedSectors(): TrackedSector[] {
  const raw = buildRaw();
  const normalizeFinancing = normalizer(raw.map((item) => item.financing));
  const normalizeInstitutions = normalizer(raw.map((item) => item.institutions));
  const normalizeEvents = normalizer(raw.map((item) => item.weightedEvents));
  const normalizeIpo = normalizer(raw.map((item) => item.ipo));
  const normalizeResearch = normalizer(raw.map((item) => item.research));

  return raw.map((item) => {
    const { tracking, base, aliases, events } = item;
    const sourceCount = new Set(events.map((event) => event.source.url)).size;
    const heat = Math.round(
      0.3 * normalizeFinancing(item.financing) +
        0.2 * normalizeInstitutions(item.institutions) +
        0.2 * normalizeEvents(item.weightedEvents) +
        0.15 * normalizeIpo(item.ipo) +
        0.15 * normalizeResearch(item.research),
    );
    const completeness = Math.min(
      100,
      Math.round(
        (events.length > 0 ? 35 : 10) +
          Math.min(events.length, 10) * 4 +
          Math.min(sourceCount, 5) * 5 +
          Math.min(tracking.keywords.length, 5) * 2,
      ),
    );
    const subsectors = unique(
      [...tracking.keywords, ...(base?.subsectors ?? [])],
      8,
    );
    const researchFocus = unique(
      [
        ...tracking.keywords,
        ...tracking.people,
        ...(base?.researchFocus ?? []),
      ],
      5,
    );

    return {
      slug: tracking.slug,
      name: tracking.name,
      definition: base?.definition ?? genericDefinition(tracking),
      subsectors: subsectors.length ? subsectors : [tracking.name],
      chain:
        base?.chain ??
        [
          { title: "基础研究", detail: "核心原理、关键论文与技术可行性" },
          { title: "工程平台", detail: "产品、基础设施与规模化能力" },
          { title: "产业应用", detail: "客户验证、商业模式与资本事件" },
        ],
      chinaLens:
        base?.chinaLens ??
        `关注中国市场中的${tracking.name}供应链、工程化速度、政策环境与商业落地。`,
      usLens:
        base?.usLens ??
        `关注美国市场中的${tracking.name}前沿研究、平台公司、资本投入与规模化部署。`,
      researchFocus: researchFocus.length
        ? researchFocus
        : ["关键技术指标", "商业化进度", "资本与监管变化"],
      risks:
        base?.risks ??
        ["技术路线尚未收敛", "产业化周期与资本开支压力", "数据、合规与供应链不确定性"],
      heat,
      completeness,
      trend:
        item.current > item.previous
          ? "up"
          : item.current < item.previous
            ? "down"
            : "flat",
      events: events.length,
      institutions: item.institutions,
      financingEvents: item.financing,
      sourceCount,
      fundingLabel: `${item.financing} 笔融资披露`,
      tracking,
      aliases,
      baseName: base?.name,
    };
  });
}

export const trackedSectors: TrackedSector[] = buildTrackedSectors();

export function getTrackedSector(slug: string): TrackedSector | undefined {
  return trackedSectors.find((sector) => sector.slug === slug);
}

export function eventsForTrackedSector(
  sector: Pick<TrackedSector, "aliases">,
): IntelligenceEvent[] {
  return intelligenceEvents.filter((event) => sector.aliases.includes(event.sector));
}
