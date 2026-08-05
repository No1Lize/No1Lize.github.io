#!/usr/bin/env python3
"""One-time presentation and boundary patch for tracked-entity research phase two."""

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


replace_once(
    "components/tracking-capture-inbox.tsx",
    '''const STATUS_LABELS: Record<TrackingCaptureStatus, string> = {\n  queued: "等待应用",\n  applied: "已开始追踪",\n  dismissed: "已忽略",\n};''',
    '''const STATUS_LABELS: Record<TrackingCaptureStatus, string> = {\n  queued: "等待应用",\n  applied: "已开始追踪",\n  dismissed: "已忽略",\n};\n\nconst ATTENTION_LABELS = {\n  1: "仅记录",\n  2: "新闻提醒",\n  3: "一般跟踪",\n  4: "重点观察",\n  5: "核心研究",\n} as const;''',
)
replace_once(
    "components/tracking-capture-inbox.tsx",
    '''              <div>\n                <dt>操作审计</dt>\n                <dd>{record.capturedBy || "未知管理员"} · {formatTime(record.capturedAt)}</dd>\n              </div>''',
    '''              <div>\n                <dt>关注等级</dt>\n                <dd>{record.attentionLevel} 星 · {ATTENTION_LABELS[record.attentionLevel]}</dd>\n              </div>\n              <div>\n                <dt>操作审计</dt>\n                <dd>{record.capturedBy || "未知管理员"} · {formatTime(record.capturedAt)}</dd>\n              </div>''',
)

append_once(
    "app/tracking/entities/[type]/[slug]/tracking-entity-detail.module.css",
    ".brief {",
    '''.brief {\n  margin: 24px 0 0;\n  border: 1px solid var(--line);\n  padding: 22px;\n  background: color-mix(in srgb, var(--green) 3%, var(--paper));\n}\n\n.brief > header {\n  display: flex;\n  align-items: flex-start;\n  justify-content: space-between;\n  gap: 24px;\n  padding-bottom: 16px;\n  border-bottom: 1px solid var(--line);\n}\n\n.brief > header h2,\n.relations h2 {\n  display: flex;\n  align-items: center;\n  gap: 8px;\n}\n\n.attentionBadge,\n.sidebarAttention {\n  display: flex;\n  align-items: center;\n  gap: 9px;\n}\n\n.attentionBadge {\n  border: 1px solid var(--green);\n  padding: 9px 11px;\n  color: var(--green);\n  white-space: nowrap;\n}\n\n.stars {\n  display: inline-flex;\n  gap: 2px;\n  color: var(--ochre);\n}\n\n.briefLead {\n  padding: 18px 0 4px;\n}\n\n.briefLead h3 {\n  margin: 0;\n  font-family: var(--font-serif);\n  font-size: clamp(25px, 3vw, 36px);\n  font-weight: 500;\n}\n\n.briefLead p {\n  max-width: 900px;\n  margin: 10px 0 0;\n  color: var(--muted);\n  line-height: 1.75;\n}\n\n.signalGrid {\n  display: grid;\n  grid-template-columns: repeat(4, minmax(0, 1fr));\n  gap: 9px;\n  margin-top: 16px;\n}\n\n.signalGrid article {\n  display: grid;\n  gap: 8px;\n  min-height: 116px;\n  border: 1px solid var(--line);\n  padding: 13px;\n  background: var(--paper);\n}\n\n.signalGrid span {\n  display: flex;\n  align-items: center;\n  gap: 6px;\n  color: var(--muted);\n  font-size: 12px;\n}\n\n.signalGrid strong {\n  font-size: 22px;\n}\n\n.signalGrid small {\n  overflow: hidden;\n  color: var(--muted);\n  line-height: 1.45;\n  text-overflow: ellipsis;\n  display: -webkit-box;\n  -webkit-line-clamp: 2;\n  -webkit-box-orient: vertical;\n}\n\n.briefColumns {\n  display: grid;\n  grid-template-columns: repeat(2, minmax(0, 1fr));\n  gap: 12px;\n  margin-top: 16px;\n}\n\n.briefColumns section {\n  border: 1px solid var(--line);\n  padding: 15px;\n  background: var(--paper);\n}\n\n.briefColumns h3 {\n  display: flex;\n  align-items: center;\n  gap: 7px;\n  margin: 0 0 10px;\n  font-size: 16px;\n}\n\n.briefColumns ul {\n  display: grid;\n  gap: 7px;\n  margin: 0;\n  padding-left: 20px;\n  color: var(--muted);\n  line-height: 1.55;\n}\n\n.briefColumns p {\n  margin: 0;\n  color: var(--muted);\n  line-height: 1.6;\n}\n\n.methodology {\n  margin: 15px 0 0;\n  padding-top: 12px;\n  border-top: 1px solid var(--line);\n  color: var(--muted);\n  font-size: 11px;\n  line-height: 1.6;\n}\n\n.sidebarAttention {\n  margin: 0 0 13px;\n  padding: 9px 0;\n  border-bottom: 1px solid var(--line);\n  color: var(--muted);\n  font-size: 12px;\n}\n\n.relations {\n  margin-top: 34px;\n}\n\n.relationGrid {\n  display: grid;\n  grid-template-columns: repeat(2, minmax(0, 1fr));\n  gap: 12px;\n  margin-top: 15px;\n}\n\n.relationGrid > article {\n  display: grid;\n  gap: 10px;\n  border: 1px solid var(--line);\n  padding: 15px;\n}\n\n.relationTop {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  gap: 8px;\n}\n\n.relationTop span,\n.relationTop em {\n  border: 1px solid var(--line);\n  padding: 4px 7px;\n  color: var(--muted);\n  font-size: 10px;\n  font-style: normal;\n}\n\n.relationTop span[data-kind="competition"] {\n  border-color: #a84b42;\n  color: #a84b42;\n}\n\n.relationTop span[data-kind="partnership"],\n.relationTop span[data-kind="leadership"] {\n  border-color: var(--green);\n  color: var(--green);\n}\n\n.relationTop em[data-confidence="contextual"] {\n  border-style: dashed;\n}\n\n.relationGrid > article > a {\n  display: flex;\n  align-items: center;\n  gap: 8px;\n  color: inherit;\n  text-decoration: none;\n}\n\n.relationGrid > article > a:hover {\n  color: var(--green);\n}\n\n.relationGrid > article > p {\n  margin: 0;\n  color: var(--muted);\n  font-size: 12px;\n  line-height: 1.55;\n}\n\n.relationEvidence {\n  display: grid;\n  gap: 7px;\n  padding-top: 10px;\n  border-top: 1px solid var(--line);\n}\n\n.relationEvidence a {\n  display: grid;\n  grid-template-columns: 1fr auto;\n  gap: 4px 8px;\n  color: inherit;\n  text-decoration: none;\n}\n\n.relationEvidence a span {\n  grid-column: 1 / -1;\n  color: var(--muted);\n  font-size: 10px;\n}\n\n.relationEvidence a strong {\n  font-size: 12px;\n  line-height: 1.45;\n}\n\n.contextOnly {\n  padding-top: 10px;\n  border-top: 1px dashed var(--line);\n}\n\n@media (max-width: 1000px) {\n  .signalGrid {\n    grid-template-columns: repeat(2, minmax(0, 1fr));\n  }\n}\n\n@media (max-width: 700px) {\n  .brief > header,\n  .relationTop {\n    align-items: flex-start;\n    flex-direction: column;\n  }\n\n  .signalGrid,\n  .briefColumns,\n  .relationGrid {\n    grid-template-columns: 1fr;\n  }\n}''',
)

append_once(
    "components/tracking-entity-directory.module.css",
    ".attention {",
    '''.attention {\n  display: flex;\n  align-items: center;\n  justify-content: space-between;\n  gap: 8px;\n  margin-top: 14px;\n  padding: 7px 9px;\n  border: 1px solid var(--line);\n  color: var(--muted);\n  font-size: 11px;\n}\n\n.attention span {\n  display: inline-flex;\n  gap: 1px;\n  color: var(--ochre);\n}\n\n.attention[data-level="4"],\n.attention[data-level="5"] {\n  border-color: var(--green);\n  color: var(--green);\n}\n\n.attention strong {\n  font-size: 11px;\n}\n''',
)

replace_once(
    "tests/tracking-entity-research.test.ts",
    '''  for (const entity of trackingResearchEntities) {\n    assert.equal(\n      trackingResearchEntity(entity.entityType, entity.slug)?.id,''',
    '''  for (const entity of trackingResearchEntities) {\n    assert.ok(entity.attentionLevel >= 1 && entity.attentionLevel <= 5);\n    assert.equal(\n      trackingResearchEntity(entity.entityType, entity.slug)?.id,''',
)
