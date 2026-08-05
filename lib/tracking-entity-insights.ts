import {
  trackingResearchEntities,
  trackingResearchHref,
  type TrackingResearchEntity,
  type TrackingResearchTimelineItem,
} from "@/lib/tracking-entity-research";

export type TrackingResearchSignalCategory =
  | "financing"
  | "regulation"
  | "competition"
  | "listing"
  | "partnership"
  | "product"
  | "technology"
  | "operations"
  | "research"
  | "other";

export type TrackingResearchSignal = {
  category: TrackingResearchSignalCategory;
  label: string;
  count: number;
  latestAt: string;
  latestTitle: string;
};

export type TrackingResearchRelationKind =
  | "competition"
  | "partnership"
  | "leadership"
  | "thematic"
  | "co-mentioned"
  | "shared-track";

export type TrackingResearchRelationEvidence = {
  title: string;
  url: string;
  eventType: string;
  eventDate: string;
  sourceName: string;
};

export type TrackingResearchRelation = {
  entity: TrackingResearchEntity;
  href: string;
  kind: TrackingResearchRelationKind;
  label: string;
  confidence: "high" | "medium" | "contextual";
  evidenceCount: number;
  sharedTracks: string[];
  evidence: TrackingResearchRelationEvidence[];
};

export type TrackingResearchBrief = {
  attentionLevel: 1 | 2 | 3 | 4 | 5;
  attentionLabel: string;
  headline: string;
  summary: string;
  signals: TrackingResearchSignal[];
  watchItems: string[];
  openQuestions: string[];
  methodology: string;
};

export const TRACKING_ATTENTION_LABELS: Record<1 | 2 | 3 | 4 | 5, string> = {
  1: "仅记录",
  2: "新闻提醒",
  3: "一般跟踪",
  4: "重点观察",
  5: "核心研究",
};

const SIGNAL_DEFINITIONS: Array<{
  category: TrackingResearchSignalCategory;
  label: string;
  pattern: RegExp;
}> = [
  {
    category: "regulation",
    label: "监管与合规",
    pattern: /监管|合规|政策|牌照|许可|法院|诉讼|执法|SEC|CFTC|FTC|antitrust|regulat|license|legal/iu,
  },
  {
    category: "financing",
    label: "融资与估值",
    pattern: /融资|募资|投资轮|估值|投资方|资本注入|funding|fundrais|raise[ds]?|valuation|series\s+[a-f]/iu,
  },
  {
    category: "listing",
    label: "上市与资本市场",
    pattern: /IPO|上市|招股|交易所|挂牌|借壳|SPAC|public company|listing/iu,
  },
  {
    category: "competition",
    label: "竞争格局",
    pattern: /竞争|竞品|对手|市场份额|争夺|rival|competitor|competitive|compete|versus|\bvs\.?\b/iu,
  },
  {
    category: "partnership",
    label: "合作与生态",
    pattern: /合作|伙伴|联盟|协议|签署|生态合作|partner|partnership|collaborat|alliance/iu,
  },
  {
    category: "product",
    label: "产品与商业化",
    pattern: /产品|发布|上线|功能|服务|平台|商业化|客户|订单|launch|release|product|service|customer/iu,
  },
  {
    category: "technology",
    label: "技术与研发",
    pattern: /技术|研发|模型|芯片|算法|专利|论文|开源|AI|technology|research|model|chip|patent|open source/iu,
  },
  {
    category: "operations",
    label: "经营与增长",
    pattern: /营收|利润|亏损|增长|用户|扩张|市场进入|组织调整|裁员|revenue|profit|loss|growth|user|expand|layoff/iu,
  },
  {
    category: "research",
    label: "研究与观点",
    pattern: /研究|观点|访谈|演讲|报告|白皮书|采访|analysis|report|interview|speech|opinion/iu,
  },
];

const RELATION_LABELS: Record<TrackingResearchRelationKind, string> = {
  competition: "竞争关系",
  partnership: "合作关系",
  leadership: "人物与组织",
  thematic: "主题关联",
  "co-mentioned": "共同出现",
  "shared-track": "共同赛道",
};

const WATCH_LABELS: Partial<Record<TrackingResearchSignalCategory, string>> = {
  financing: "融资进度、估值变化和新增投资方",
  regulation: "监管政策、牌照和合规边界",
  competition: "竞争对手、市场份额和差异化",
  listing: "上市路径、交易所披露和资本市场窗口",
  partnership: "关键合作伙伴和生态扩张",
  product: "产品迭代、客户采用和商业化进度",
  technology: "技术路线、研发里程碑和知识产权",
  operations: "用户增长、收入质量和组织变化",
  research: "核心观点与公开研究材料",
};

function text(value: unknown, limit = 1_200) {
  return String(value ?? "").normalize("NFKC").replace(/\s+/gu, " ").trim().slice(0, limit);
}

function unique(values: Iterable<string>, limit = 20) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = text(raw, 500);
    const key = value.toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function itemText(item: TrackingResearchTimelineItem) {
  return `${item.eventType} ${item.title} ${item.summary}`;
}

export function classifyTrackingResearchTimelineItem(
  item: TrackingResearchTimelineItem,
): TrackingResearchSignalCategory {
  const combined = itemText(item);
  return SIGNAL_DEFINITIONS.find((definition) => definition.pattern.test(combined))?.category ?? "other";
}

function signalLabel(category: TrackingResearchSignalCategory) {
  return SIGNAL_DEFINITIONS.find((definition) => definition.category === category)?.label ?? "其他动态";
}

export function trackingResearchSignals(entity: TrackingResearchEntity): TrackingResearchSignal[] {
  const groups = new Map<TrackingResearchSignalCategory, TrackingResearchTimelineItem[]>();
  for (const item of entity.timeline) {
    const category = classifyTrackingResearchTimelineItem(item);
    groups.set(category, [...(groups.get(category) ?? []), item]);
  }
  return [...groups.entries()]
    .map(([category, items]) => {
      const sorted = [...items].sort((left, right) => right.sortAt.localeCompare(left.sortAt));
      return {
        category,
        label: signalLabel(category),
        count: sorted.length,
        latestAt: sorted[0]?.sortAt ?? "",
        latestTitle: sorted[0]?.title ?? "",
      } satisfies TrackingResearchSignal;
    })
    .sort((left, right) =>
      right.count - left.count ||
      right.latestAt.localeCompare(left.latestAt) ||
      left.label.localeCompare(right.label, "zh-CN"),
    );
}

function normalizeIdentity(value: string) {
  return text(value, 500)
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function strongAlias(alias: string) {
  const normalized = normalizeIdentity(alias);
  if (!normalized) return false;
  return /[\u3400-\u9fff]/u.test(normalized) ? normalized.length >= 3 : normalized.length >= 4;
}

function itemMentionsEntity(item: TrackingResearchTimelineItem, entity: TrackingResearchEntity) {
  const combined = itemText(item);
  return entity.aliases.some((alias) => {
    if (!strongAlias(alias)) return false;
    const normalizedAlias = normalizeIdentity(alias);
    if (/[\u3400-\u9fff]/u.test(normalizedAlias)) {
      return normalizeIdentity(combined).includes(normalizedAlias);
    }
    const escaped = text(alias, 300).replace(/[.*+?^${}()|[\]\\]/gu, "\\$&");
    return new RegExp(`(^|[^a-z0-9])${escaped}(?=$|[^a-z0-9])`, "iu").test(combined);
  });
}

type IndexedTimeline = {
  entity: TrackingResearchEntity;
  item: TrackingResearchTimelineItem;
};

const timelineByUrl = new Map<string, IndexedTimeline[]>();
for (const entity of trackingResearchEntities) {
  for (const item of entity.timeline) {
    if (!item.url) continue;
    timelineByUrl.set(item.url, [...(timelineByUrl.get(item.url) ?? []), { entity, item }]);
  }
}

function relationKind(
  entity: TrackingResearchEntity,
  related: TrackingResearchEntity,
  evidence: TrackingResearchTimelineItem[],
): TrackingResearchRelationKind {
  const combined = evidence.map(itemText).join(" ");
  if (
    entity.entityType === "company" &&
    related.entityType === "company" &&
    /竞争|竞品|对手|市场份额|rival|competitor|competitive|compete|versus|\bvs\.?\b/iu.test(combined)
  ) {
    return "competition";
  }
  if (
    entity.entityType === "company" &&
    related.entityType === "company" &&
    /合作|伙伴|联盟|协议|partner|partnership|collaborat|alliance/iu.test(combined)
  ) {
    return "partnership";
  }
  if (
    new Set([entity.entityType, related.entityType]).has("company") &&
    new Set([entity.entityType, related.entityType]).has("person") &&
    /创始人|联合创始人|CEO|CTO|董事|高管|founder|chief executive|executive|chair/iu.test(combined)
  ) {
    return "leadership";
  }
  if (entity.entityType === "topic" || related.entityType === "topic") return "thematic";
  return "co-mentioned";
}

function relationPriority(kind: TrackingResearchRelationKind) {
  if (kind === "competition") return 6;
  if (kind === "partnership") return 5;
  if (kind === "leadership") return 4;
  if (kind === "thematic") return 3;
  if (kind === "co-mentioned") return 2;
  return 1;
}

export function trackingResearchRelations(
  entity: TrackingResearchEntity,
  limit = 10,
): TrackingResearchRelation[] {
  const direct = new Map<string, { entity: TrackingResearchEntity; items: TrackingResearchTimelineItem[] }>();
  for (const item of entity.timeline) {
    const rows = timelineByUrl.get(item.url) ?? [];
    for (const row of rows) {
      if (row.entity.id === entity.id) continue;
      const manualEvidence = item.origin === "manual-capture" || row.item.origin === "manual-capture";
      if (!manualEvidence && (!itemMentionsEntity(item, entity) || !itemMentionsEntity(row.item, row.entity))) {
        continue;
      }
      const current = direct.get(row.entity.id) ?? { entity: row.entity, items: [] };
      if (!current.items.some((candidate) => candidate.url === item.url)) current.items.push(item);
      direct.set(row.entity.id, current);
    }
  }

  const relations: TrackingResearchRelation[] = [...direct.values()].map((row) => {
    const items = [...row.items].sort((left, right) => right.sortAt.localeCompare(left.sortAt));
    const kind = relationKind(entity, row.entity, items);
    const sharedTracks = row.entity.trackNames.filter((track) => entity.trackNames.includes(track));
    return {
      entity: row.entity,
      href: trackingResearchHref(row.entity),
      kind,
      label: RELATION_LABELS[kind],
      confidence: kind === "competition" || kind === "partnership" || items.length >= 2 ? "high" : "medium",
      evidenceCount: items.length,
      sharedTracks,
      evidence: items.slice(0, 3).map((item) => ({
        title: item.title,
        url: item.url,
        eventType: item.eventType,
        eventDate: item.eventDate || item.observedAt.slice(0, 10),
        sourceName: item.sourceName,
      })),
    } satisfies TrackingResearchRelation;
  });

  const directIds = new Set(relations.map((relation) => relation.entity.id));
  for (const candidate of trackingResearchEntities) {
    if (candidate.id === entity.id || directIds.has(candidate.id)) continue;
    const sharedTracks = candidate.trackNames.filter((track) => entity.trackNames.includes(track));
    if (!sharedTracks.length) continue;
    relations.push({
      entity: candidate,
      href: trackingResearchHref(candidate),
      kind: "shared-track",
      label: RELATION_LABELS["shared-track"],
      confidence: "contextual",
      evidenceCount: 0,
      sharedTracks,
      evidence: [],
    });
  }

  return relations
    .sort((left, right) =>
      relationPriority(right.kind) - relationPriority(left.kind) ||
      right.evidenceCount - left.evidenceCount ||
      right.sharedTracks.length - left.sharedTracks.length ||
      right.entity.lastActivityAt.localeCompare(left.entity.lastActivityAt),
    )
    .slice(0, limit);
}

function normalizedAttentionLevel(entity: TrackingResearchEntity): 1 | 2 | 3 | 4 | 5 {
  const value = Number((entity as TrackingResearchEntity & { attentionLevel?: number }).attentionLevel ?? 0);
  if (Number.isInteger(value) && value >= 1 && value <= 5) return value as 1 | 2 | 3 | 4 | 5;
  if (entity.captureCount > 0 || entity.reasons.length > 0) return 3;
  return 2;
}

export function trackingResearchBrief(entity: TrackingResearchEntity): TrackingResearchBrief {
  const attentionLevel = normalizedAttentionLevel(entity);
  const signals = trackingResearchSignals(entity);
  const primarySignals = signals.filter((signal) => signal.category !== "other").slice(0, 4);
  const latest = entity.timeline[0];
  const relations = trackingResearchRelations(entity, 8);
  const evidenceCount = entity.timeline.length;
  const signalText = primarySignals.length
    ? primarySignals.slice(0, 2).map((signal) => signal.label).join("、")
    : "公开活动";
  const stateText = entity.state === "formal"
    ? "已有正式档案"
    : entity.state === "candidate"
      ? "仍处于候选审核阶段"
      : "当前仅处于追踪状态";
  const headline = latest
    ? `${entity.name}近期以${signalText}信号为主`
    : `${entity.name}已纳入${entity.trackNames.join("、") || "当前赛道"}追踪`;
  const summary = latest
    ? `系统基于${evidenceCount}条可追溯时间线记录自动汇总：最近一条动态为“${latest.title}”，${stateText}。`
    : `该对象${stateText}，尚未形成可追溯公开事件时间线。`;

  const watchItems = unique([
    ...entity.reasons,
    ...primarySignals.map((signal) => WATCH_LABELS[signal.category] ?? signal.label),
    ...(relations.some((relation) => relation.kind === "competition")
      ? ["已识别竞争关系，持续核对竞争证据和市场变化"]
      : []),
    ...(entity.state !== "formal" && entity.entityType !== "topic"
      ? ["规范实体、官方主页和正式档案补全"]
      : []),
  ], 6);

  const openQuestions = unique([
    ...(entity.state !== "formal" && entity.entityType !== "topic"
      ? ["规范实体边界和官方来源是否已经完成核验？"]
      : []),
    ...(entity.captureCount === 0
      ? ["是否需要补充人工关注原因、研究假设和首条关键证据？"]
      : []),
    ...(entity.entityType === "company" && !signals.some((signal) => signal.category === "financing")
      ? ["近期融资、估值和投资方是否存在新的可核对变化？"]
      : []),
    ...(!relations.some((relation) => relation.evidenceCount > 0)
      ? ["是否存在可以由原文共同出现证明的竞争、合作或人物关系？"]
      : []),
  ], 5);

  return {
    attentionLevel,
    attentionLabel: TRACKING_ATTENTION_LABELS[attentionLevel],
    headline,
    summary,
    signals: primarySignals,
    watchItems,
    openQuestions,
    methodology: "基于版本化追踪配置、人工文章采集和可追溯公开时间线规则生成；不引入没有来源支持的事实。",
  };
}
