#!/usr/bin/env python3
"""One-time patch for tracked-entity research phase two."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{relative}: patch target not found: {old[:140]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(relative: str, marker: str, content: str) -> None:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + content.strip() + "\n", encoding="utf-8")


# Capture schema and persistence.
replace_once(
    "lib/tracking-capture.ts",
    'export type TrackingCaptureStatus = "queued" | "applied" | "dismissed";\n',
    'export type TrackingCaptureStatus = "queued" | "applied" | "dismissed";\nexport type TrackingAttentionLevel = 1 | 2 | 3 | 4 | 5;\n',
)
replace_once(
    "lib/tracking-capture.ts",
    '''  appliedTo: string[];\n  reasons: string[];''',
    '''  appliedTo: string[];\n  attentionLevel: TrackingAttentionLevel;\n  reasons: string[];''',
)
replace_once(
    "lib/tracking-capture.ts",
    '''  newTrackName?: string;\n  reasons?: string[];''',
    '''  newTrackName?: string;\n  attentionLevel?: TrackingAttentionLevel;\n  reasons?: string[];''',
)
replace_once(
    "lib/tracking-capture.ts",
    '''function uniqueStrings(value: unknown, maxItems = 40): string[] {\n  if (!Array.isArray(value)) return [];\n  const result: string[] = [];\n  const seen = new Set<string>();\n  for (const raw of value) {\n    const item = cleanText(raw, 160);\n    const key = item.toLocaleLowerCase("zh-CN");\n    if (!item || seen.has(key)) continue;\n    result.push(item);\n    seen.add(key);\n    if (result.length >= maxItems) break;\n  }\n  return result;\n}\n''',
    '''function uniqueStrings(value: unknown, maxItems = 40): string[] {\n  if (!Array.isArray(value)) return [];\n  const result: string[] = [];\n  const seen = new Set<string>();\n  for (const raw of value) {\n    const item = cleanText(raw, 160);\n    const key = item.toLocaleLowerCase("zh-CN");\n    if (!item || seen.has(key)) continue;\n    result.push(item);\n    seen.add(key);\n    if (result.length >= maxItems) break;\n  }\n  return result;\n}\n\nexport function normalizeTrackingAttentionLevel(value: unknown): TrackingAttentionLevel {\n  const level = Math.round(Number(value));\n  return level >= 1 && level <= 5 ? (level as TrackingAttentionLevel) : 3;\n}\n''',
)
replace_once(
    "lib/tracking-capture.ts",
    '''    status,\n    appliedTo: uniqueStrings(raw.appliedTo, 40),\n    reasons: uniqueStrings(raw.reasons, 12),''',
    '''    status,\n    appliedTo: uniqueStrings(raw.appliedTo, 40),\n    attentionLevel: normalizeTrackingAttentionLevel(raw.attentionLevel),\n    reasons: uniqueStrings(raw.reasons, 12),''',
)
replace_once(
    "lib/tracking-capture.ts",
    '''      status: "applied",\n      appliedTo,\n      reasons: uniqueStrings(input.reasons ?? [], 12),''',
    '''      status: "applied",\n      appliedTo,\n      attentionLevel: normalizeTrackingAttentionLevel(input.attentionLevel),\n      reasons: uniqueStrings(input.reasons ?? [], 12),''',
)

# Capture drawer attention control.
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''  LoaderCircle,\n  Plus,\n  UserRound,''',
    '''  LoaderCircle,\n  Plus,\n  Star,\n  UserRound,''',
)
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''  type TrackingCaptureEntityDraft,\n  type TrackingCaptureEntityType,''',
    '''  type TrackingAttentionLevel,\n  type TrackingCaptureEntityDraft,\n  type TrackingCaptureEntityType,''',
)
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''const RESEARCH_REASON_OPTIONS = [\n  "融资机会",\n  "技术突破",\n  "商业模式创新",\n  "市场竞争",\n  "IPO可能",\n  "监管变化",\n  "个人研究兴趣",\n] as const;\n''',
    '''const RESEARCH_REASON_OPTIONS = [\n  "融资机会",\n  "技术突破",\n  "商业模式创新",\n  "市场竞争",\n  "IPO可能",\n  "监管变化",\n  "个人研究兴趣",\n] as const;\n\nconst ATTENTION_OPTIONS: Array<{ level: TrackingAttentionLevel; label: string }> = [\n  { level: 1, label: "仅记录" },\n  { level: 2, label: "新闻提醒" },\n  { level: 3, label: "一般跟踪" },\n  { level: 4, label: "重点观察" },\n  { level: 5, label: "核心研究" },\n];\n''',
)
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);\n  const [researchNote, setResearchNote] = useState("");''',
    '''  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);\n  const [researchNote, setResearchNote] = useState("");\n  const [attentionLevel, setAttentionLevel] = useState<TrackingAttentionLevel>(3);''',
)
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''          newTrackName,\n          reasons: selectedReasons,''',
    '''          newTrackName,\n          attentionLevel,\n          reasons: selectedReasons,''',
)
replace_once(
    "components/intelligence-tracking-capture-controls.tsx",
    '''          <div className={styles.reasonGrid}>\n            {RESEARCH_REASON_OPTIONS.map((reason) => (''',
    '''          <div className={styles.attentionControl}>\n            <strong>关注等级</strong>\n            <div>\n              {ATTENTION_OPTIONS.map((option) => (\n                <button\n                  type="button"\n                  key={option.level}\n                  data-selected={attentionLevel === option.level}\n                  onClick={() => setAttentionLevel(option.level)}\n                  aria-label={`关注等级 ${option.level}：${option.label}`}\n                >\n                  <span>{Array.from({ length: option.level }, (_, index) => (\n                    <Star key={index} size={11} fill="currentColor" />\n                  ))}</span>\n                  <small>{option.label}</small>\n                </button>\n              ))}\n            </div>\n          </div>\n          <div className={styles.reasonGrid}>\n            {RESEARCH_REASON_OPTIONS.map((reason) => (''',
)
append_once(
    "components/intelligence-tracking-capture-controls.module.css",
    ".attentionControl {",
    '''.attentionControl {\n  display: grid;\n  gap: 8px;\n  margin-bottom: 14px;\n}\n\n.attentionControl > strong {\n  color: var(--muted);\n  font-size: 12px;\n  font-weight: 500;\n}\n\n.attentionControl > div {\n  display: grid;\n  grid-template-columns: repeat(5, minmax(0, 1fr));\n  gap: 6px;\n}\n\n.attentionControl button {\n  display: grid;\n  justify-items: center;\n  gap: 5px;\n  min-height: 48px;\n  padding: 7px 4px;\n  border: 1px solid var(--border-soft);\n  background: var(--surface-2);\n  color: var(--muted);\n  font: inherit;\n  cursor: pointer;\n}\n\n.attentionControl button[data-selected="true"] {\n  border-color: var(--green);\n  background: color-mix(in srgb, var(--green) 10%, var(--surface));\n  color: var(--green-bright);\n}\n\n.attentionControl button span {\n  display: flex;\n  justify-content: center;\n  gap: 1px;\n}\n\n.attentionControl button small {\n  font-size: 10px;\n}\n\n@media (max-width: 760px) {\n  .attentionControl > div {\n    grid-template-columns: repeat(2, minmax(0, 1fr));\n  }\n}''',
)

# Aggregate attention on research entities.
replace_once(
    "lib/tracking-entity-research.ts",
    '''  articleCount: number;\n  reasons: string[];''',
    '''  articleCount: number;\n  attentionLevel: 1 | 2 | 3 | 4 | 5;\n  reasons: string[];''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''  captures: TrackingCaptureRecord[];\n  reasons: Set<string>;''',
    '''  captures: TrackingCaptureRecord[];\n  attentionLevels: number[];\n  reasons: Set<string>;''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''        captures: [],\n        reasons: new Set(),''',
    '''        captures: [],\n        attentionLevels: [],\n        reasons: new Set(),''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''      entity.captures.push(options.capture);\n      options.capture.aliases.forEach((alias) => entity?.aliases.add(alias));''',
    '''      entity.captures.push(options.capture);\n      entity.attentionLevels.push(options.capture.attentionLevel);\n      options.capture.aliases.forEach((alias) => entity?.aliases.add(alias));''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''    const articleCount = timeline.filter((item) => item.origin === "intelligence").length;\n    return {''',
    '''    const articleCount = timeline.filter((item) => item.origin === "intelligence").length;\n    const attentionValue = entity.attentionLevels.length\n      ? Math.max(...entity.attentionLevels)\n      : 2;\n    const attentionLevel = Math.max(1, Math.min(5, attentionValue)) as 1 | 2 | 3 | 4 | 5;\n    return {''',
)
replace_once(
    "lib/tracking-entity-research.ts",
    '''      captureCount: entity.captures.length,\n      articleCount,\n      reasons: unique(entity.reasons),''',
    '''      captureCount: entity.captures.length,\n      articleCount,\n      attentionLevel,\n      reasons: unique(entity.reasons),''',
)

# Capture tests cover explicit and legacy attention behavior.
replace_once(
    "tests/tracking-capture.test.ts",
    '''    newTrackName: "预测市场",\n    source,''',
    '''    newTrackName: "预测市场",\n    attentionLevel: 5,\n    source,''',
)
replace_once(
    "tests/tracking-capture.test.ts",
    '''  assert.equal(result.records[0].status, "applied");\n  assert.deepEqual(result.records[0].reasons,''',
    '''  assert.equal(result.records[0].status, "applied");\n  assert.equal(result.records[0].attentionLevel, 5);\n  assert.deepEqual(result.records[0].reasons,''',
)
replace_once(
    "tests/tracking-capture.test.ts",
    '''  assert.deepEqual(inbox.records[0].reasons, []);\n  assert.equal(inbox.records[0].note, "");''',
    '''  assert.equal(inbox.records[0].attentionLevel, 3);\n  assert.deepEqual(inbox.records[0].reasons, []);\n  assert.equal(inbox.records[0].note, "");''',
)
