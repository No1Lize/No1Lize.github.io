#!/usr/bin/env python3
"""One-time integration of editable priority and analyst notes into entity research."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{relative}: patch target not found: {old[:100]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Research aggregation: load persistent records, expose priority and add analyst notes to timeline.
replace_once(
    "lib/tracking-entity-research.ts",
    'import rawInbox from "@/config/tracking_capture_inbox.json";\n',
    'import rawInbox from "@/config/tracking_capture_inbox.json";\nimport rawEntityRecords from "@/config/tracking_entity_records.json";\n',
)
replace_once(
    "lib/tracking-entity-research.ts",
    'import { slugifyTrack, userTrackingConfig } from "@/lib/user-tracking";\n',
    '''import {\n  normalizeTrackingEntityRecordManifest,\n  trackingEntityPriorityLabel,\n  trackingEntityPriorityStars,\n  type TrackingEntityAnalystNote,\n  type TrackingEntityResearchRecord,\n} from "@/lib/tracking-entity-records";\nimport { slugifyTrack, userTrackingConfig } from "@/lib/user-tracking";\n''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    'export type TrackingResearchTimelineOrigin = "manual-capture" | "intelligence";',
    'export type TrackingResearchTimelineOrigin = "manual-capture" | "intelligence" | "analyst-note";',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  reasons: string[];\n  notes: string[];\n  timeline: TrackingResearchTimelineItem[];''',
    '''  reasons: string[];\n  notes: string[];\n  priority: number;\n  priorityLabel: string;\n  priorityStars: string;\n  researchThesis: string;\n  analystNotes: TrackingEntityAnalystNote[];\n  researchRecord?: TrackingEntityResearchRecord;\n  timeline: TrackingResearchTimelineItem[];''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  notes: Set<string>;\n  configured: boolean;''',
    '''  notes: Set<string>;\n  researchRecord?: TrackingEntityResearchRecord;\n  configured: boolean;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''const captureInbox = normalizeTrackingCaptureInbox(rawInbox);\nconst articlesPayload = rawArticles as RawArticlePayload;''',
    '''const captureInbox = normalizeTrackingCaptureInbox(rawInbox);\nconst entityRecordManifest = normalizeTrackingEntityRecordManifest(rawEntityRecords);\nconst articlesPayload = rawArticles as RawArticlePayload;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''      configured?: boolean;\n      capture?: TrackingCaptureRecord;''',
    '''      configured?: boolean;\n      capture?: TrackingCaptureRecord;\n      record?: TrackingEntityResearchRecord;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''        notes: new Set(),\n        configured: false,''',
    '''        notes: new Set(),\n        researchRecord: undefined,\n        configured: false,''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''      if (options.capture.note) entity.notes.add(options.capture.note);\n    }\n    return entity;''',
    '''      if (options.capture.note) entity.notes.add(options.capture.note);\n    }\n    if (options.record) {\n      entity.researchRecord = options.record;\n      options.record.reasons.forEach((reason) => entity?.reasons.add(reason));\n    }\n    return entity;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  for (const capture of captureInbox.records) {\n    if (capture.status === "dismissed") continue;\n    ensure(capture.entityType, capture.canonicalName, { capture });\n  }\n\n  return [...map.values()];''',
    '''  for (const capture of captureInbox.records) {\n    if (capture.status === "dismissed") continue;\n    ensure(capture.entityType, capture.canonicalName, { capture });\n  }\n\n  for (const record of Object.values(entityRecordManifest.records)) {\n    ensure(record.entityType, record.canonicalName, { record });\n  }\n\n  return [...map.values()];''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''function buildTimeline(entity: MutableEntity) {\n  const byUrl = new Map<string, TrackingResearchTimelineItem>();''',
    '''function analystNoteTimelineItem(\n  entity: MutableEntity,\n  note: TrackingEntityAnalystNote,\n): TrackingResearchTimelineItem {\n  return {\n    id: note.id,\n    origin: "analyst-note",\n    title: `${entity.name} 研究笔记`,\n    summary: note.body,\n    url: "",\n    sourceName: "VCIQ 研究记录",\n    eventType: "研究笔记",\n    channel: "research",\n    channelLabel: "人工研究",\n    eventDate: dateOnly(note.createdAt),\n    observedAt: note.createdAt,\n    sortAt: note.createdAt,\n    capturedBy: note.createdBy,\n    captureIds: [],\n    reasons: [],\n    note: "",\n  };\n}\n\nfunction buildTimeline(entity: MutableEntity) {\n  const byUrl = new Map<string, TrackingResearchTimelineItem>();''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  return [...byUrl.values()]\n    .sort((left, right) =>''',
    '''  for (const note of entity.researchRecord?.notes ?? []) {\n    byUrl.set(`analyst:${note.id}`, analystNoteTimelineItem(entity, note));\n  }\n\n  return [...byUrl.values()]\n    .sort((left, right) =>''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''function entitySummary(entity: MutableEntity) {\n  if (entity.formalSummary) return entity.formalSummary;''',
    '''function entitySummary(entity: MutableEntity) {\n  if (entity.researchRecord?.thesis) return entity.researchRecord.thesis;\n  if (entity.formalSummary) return entity.formalSummary;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''    const captureDates = entity.captures.map((capture) => capture.capturedAt).filter(Boolean).sort();\n    const firstTrackedAt = captureDates[0] ?? "";\n    const lastActivityAt = timeline[0]?.sortAt ?? firstTrackedAt;''',
    '''    const captureDates = entity.captures.map((capture) => capture.capturedAt).filter(Boolean);\n    const recordDates = [\n      entity.researchRecord?.createdAt ?? "",\n      ...(entity.researchRecord?.notes ?? []).map((note) => note.createdAt),\n    ].filter(Boolean);\n    const firstTrackedAt = [...captureDates, ...recordDates].sort()[0] ?? "";\n    const lastActivityAt = timeline[0]?.sortAt ?? firstTrackedAt;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''      reasons: unique(entity.reasons),\n      notes: unique(entity.notes),\n      timeline,''',
    '''      reasons: unique(entity.reasons),\n      notes: unique(entity.notes),\n      priority: entity.researchRecord?.priority ?? 0,\n      priorityLabel: trackingEntityPriorityLabel(entity.researchRecord?.priority ?? 0),\n      priorityStars: trackingEntityPriorityStars(entity.researchRecord?.priority ?? 0),\n      researchThesis: entity.researchRecord?.thesis ?? "",\n      analystNotes: entity.researchRecord?.notes ?? [],\n      researchRecord: entity.researchRecord,\n      timeline,''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  capturedCount: trackingResearchEntities.filter((entity) => entity.captureCount > 0).length,\n};''',
    '''  capturedCount: trackingResearchEntities.filter((entity) => entity.captureCount > 0).length,\n  priorityCount: trackingResearchEntities.filter((entity) => entity.priority >= 4).length,\n  noteCount: trackingResearchEntities.reduce((total, entity) => total + entity.analystNotes.length, 0),\n};''',
)

# Directory page and cards: expose priority and let analysts sort by it.
replace_once(
    "app/tracking/entities/page.tsx",
    '''  reasons: entity.reasons,\n}));''',
    '''  reasons: entity.reasons,\n  priority: entity.priority,\n  priorityLabel: entity.priorityLabel,\n  priorityStars: entity.priorityStars,\n}));''',
)
replace_once(
    "app/tracking/entities/page.tsx",
    '''          <div><dt>人工采集</dt><dd>{trackingResearchStats.capturedCount}</dd></div>\n        </dl>''',
    '''          <div><dt>人工采集</dt><dd>{trackingResearchStats.capturedCount}</dd></div>\n          <div><dt>重点研究</dt><dd>{trackingResearchStats.priorityCount}</dd></div>\n        </dl>''',
)
replace_once(
    "components/tracking-entity-directory.tsx",
    '''  reasons: string[];\n};''',
    '''  reasons: string[];\n  priority: number;\n  priorityLabel: string;\n  priorityStars: string;\n};''',
)
replace_once(
    "components/tracking-entity-directory.tsx",
    'type SortOrder = "activity" | "name" | "evidence";',
    'type SortOrder = "activity" | "name" | "evidence" | "priority";',
)
replace_once(
    "components/tracking-entity-directory.tsx",
    '''        if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-CN");\n        if (sortOrder === "evidence") {''',
    '''        if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-CN");\n        if (sortOrder === "priority") {\n          return (\n            right.priority - left.priority ||\n            right.lastActivityAt.localeCompare(left.lastActivityAt)\n          );\n        }\n        if (sortOrder === "evidence") {''',
)
replace_once(
    "components/tracking-entity-directory.tsx",
    '''          <option value="activity">最近活动优先</option>\n          <option value="evidence">证据数量优先</option>''',
    '''          <option value="activity">最近活动优先</option>\n          <option value="priority">关注等级优先</option>\n          <option value="evidence">证据数量优先</option>''',
)
replace_once(
    "components/tracking-entity-directory.tsx",
    '''              <em data-state={item.state}>{STATE_LABELS[item.state]}</em>\n            </div>''',
    '''              <div className={styles.cardStatus}>\n                <em data-state={item.state}>{STATE_LABELS[item.state]}</em>\n                {item.priority ? (\n                  <small title={item.priorityLabel}>{item.priorityStars}</small>\n                ) : null}\n              </div>\n            </div>''',
)
replace_once(
    "components/tracking-entity-directory.module.css",
    '''.cardTop > span,\n.cardTop > em {''',
    '''.cardTop > span,\n.cardStatus > em {''',
)
replace_once(
    "components/tracking-entity-directory.module.css",
    '''.cardTop > em {\n  border: 1px solid var(--line);''',
    '''.cardStatus {\n  display: flex;\n  align-items: center;\n  gap: 7px;\n}\n\n.cardStatus > em {\n  border: 1px solid var(--line);''',
)
replace_once(
    "components/tracking-entity-directory.module.css",
    '''.cardTop > em[data-state="formal"] {''',
    '''.cardStatus > small {\n  color: var(--ochre);\n  font-size: 11px;\n  letter-spacing: 0.02em;\n}\n\n.cardStatus > em[data-state="formal"] {''',
)
replace_once(
    "components/tracking-entity-directory.module.css",
    '''.cardTop > em[data-state="candidate"] {''',
    '''.cardStatus > em[data-state="candidate"] {''',
)

# Detail page: editable analyst workspace, priority display and analyst-note timeline support.
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    'import {\n  relatedTrackingResearchEntities,',
    'import { TrackingEntityResearchEditor } from "@/components/tracking-entity-research-editor";\nimport {\n  relatedTrackingResearchEntities,',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''            {entity.trackNames.map((track) => <span key={track}>{track}</span>)}\n            {entity.candidateStatus ? <span>候选状态：{entity.candidateStatus}</span> : null}''',
    '''            {entity.trackNames.map((track) => <span key={track}>{track}</span>)}\n            {entity.priority ? <span>{entity.priorityStars} · {entity.priorityLabel}</span> : null}\n            {entity.candidateStatus ? <span>候选状态：{entity.candidateStatus}</span> : null}''',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''        <div><span><GitBranch size={16} />最近活动</span><strong>{displayDate(entity.lastActivityAt)}</strong></div>\n      </section>''',
    '''        <div><span><GitBranch size={16} />最近活动</span><strong>{displayDate(entity.lastActivityAt)}</strong></div>\n        <div><span><Star size={16} />关注等级</span><strong>{entity.priority || "未设置"}</strong></div>\n      </section>''',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''            {entity.notes.length ? (\n              <div className={styles.notes}>''',
    '''            {entity.researchThesis ? (\n              <div className={styles.notes}>\n                <strong>当前研究判断</strong>\n                <p>{entity.researchThesis}</p>\n              </div>\n            ) : null}\n            {entity.notes.length ? (\n              <div className={styles.notes}>''',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''          <section>\n            <p className="section-index">IDENTITY</p>''',
    '''          <TrackingEntityResearchEditor\n            entityId={entity.id}\n            entityType={entity.entityType}\n            entityName={entity.name}\n            initialRecord={entity.researchRecord}\n          />\n\n          <section>\n            <p className="section-index">IDENTITY</p>''',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''                  <span>{item.origin === "manual-capture" ? "人工发现" : "公开动态"}</span>''',
    '''                  <span>{\n                    item.origin === "manual-capture"\n                      ? "人工发现"\n                      : item.origin === "analyst-note"\n                        ? "研究笔记"\n                        : "公开动态"\n                  }</span>''',
)
replace_once(
    "app/tracking/entities/[type]/[slug]/page.tsx",
    '''                    <a href={item.url} target="_blank" rel="noreferrer">\n                      查看原文<ExternalLink size={13} aria-hidden="true" />\n                    </a>''',
    '''                    {item.url ? (\n                      <a href={item.url} target="_blank" rel="noreferrer">\n                        查看原文<ExternalLink size={13} aria-hidden="true" />\n                      </a>\n                    ) : null}''',
)

# Timeline URL uniqueness applies only to sourced records; analyst notes intentionally have no URL.
replace_once(
    "tests/tracking-entity-research.test.ts",
    '''    const urls = entity.timeline.map((item) => item.url);''',
    '''    const urls = entity.timeline.map((item) => item.url).filter(Boolean);''',
)
