#!/usr/bin/env python3
"""One-time integration for tracked entity reasons, notes and research links."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"{path}: patch target not found: {old[:120]!r}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_once(path: str, marker: str, addition: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if addition.strip() in text:
        return
    if marker not in text:
        raise SystemExit(f"{path}: append marker not found")
    target.write_text(text.replace(marker, addition + "\n\n" + marker, 1), encoding="utf-8")


def patch_capture_model() -> None:
    path = "lib/tracking-capture.ts"
    replace_once(
        path,
        '''  status: TrackingCaptureStatus;\n  appliedTo: string[];\n};''',
        '''  status: TrackingCaptureStatus;\n  appliedTo: string[];\n  reasons: string[];\n  note: string;\n};''',
    )
    replace_once(
        path,
        '''  selectedTrackSlugs: string[];\n  newTrackName?: string;\n  source: TrackingCaptureSource;''',
        '''  selectedTrackSlugs: string[];\n  newTrackName?: string;\n  reasons?: string[];\n  note?: string;\n  source: TrackingCaptureSource;''',
    )
    replace_once(
        path,
        '''    status,\n    appliedTo: uniqueStrings(raw.appliedTo, 40),\n  };''',
        '''    status,\n    appliedTo: uniqueStrings(raw.appliedTo, 40),\n    reasons: uniqueStrings(raw.reasons, 12),\n    note: cleanText(raw.note, 800),\n  };''',
    )
    replace_once(
        path,
        '''      status: "applied",\n      appliedTo,\n    });''',
        '''      status: "applied",\n      appliedTo,\n      reasons: uniqueStrings(input.reasons ?? [], 12),\n      note: cleanText(input.note, 800),\n    });''',
    )


def patch_capture_drawer() -> None:
    path = "components/intelligence-tracking-capture-controls.tsx"
    replace_once(
        path,
        '''const LATIN_STOPWORDS = new Set([\n  "AI",''',
        '''const RESEARCH_REASON_OPTIONS = [\n  "融资机会",\n  "技术突破",\n  "商业模式创新",\n  "市场竞争",\n  "IPO可能",\n  "监管变化",\n  "个人研究兴趣",\n] as const;\n\nconst LATIN_STOPWORDS = new Set([\n  "AI",''',
    )
    replace_once(
        path,
        '''  const [newTrackName, setNewTrackName] = useState("");\n  const [token, setToken] = useState(() =>''',
        '''  const [newTrackName, setNewTrackName] = useState("");\n  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);\n  const [researchNote, setResearchNote] = useState("");\n  const [token, setToken] = useState(() =>''',
    )
    replace_once(
        path,
        '''  function toggleTrack(slug: string) {\n    setSelectedTrackSlugs((current) =>\n      current.includes(slug)\n        ? current.filter((candidate) => candidate !== slug)\n        : [...current, slug],\n    );\n  }\n\n  async function submit() {''',
        '''  function toggleTrack(slug: string) {\n    setSelectedTrackSlugs((current) =>\n      current.includes(slug)\n        ? current.filter((candidate) => candidate !== slug)\n        : [...current, slug],\n    );\n  }\n\n  function toggleReason(reason: string) {\n    setSelectedReasons((current) =>\n      current.includes(reason)\n        ? current.filter((candidate) => candidate !== reason)\n        : [...current, reason],\n    );\n  }\n\n  async function submit() {''',
    )
    replace_once(
        path,
        '''          selectedTrackSlugs,\n          newTrackName,\n          source: item,''',
        '''          selectedTrackSlugs,\n          newTrackName,\n          reasons: selectedReasons,\n          note: researchNote,\n          source: item,''',
    )
    replace_once(
        path,
        '''        <section className={styles.section}>\n          <div className={styles.sectionHeading}>\n            <div>\n              <p>03 / ADMIN COMMIT</p>\n              <h3>管理员同步</h3>''',
        '''        <section className={styles.section}>\n          <div className={styles.sectionHeading}>\n            <div>\n              <p>03 / RESEARCH INTENT</p>\n              <h3>为什么关注</h3>\n            </div>\n            <span>{selectedReasons.length} 个原因</span>\n          </div>\n          <div className={styles.reasonGrid}>\n            {RESEARCH_REASON_OPTIONS.map((reason) => (\n              <label key={reason} data-selected={selectedReasons.includes(reason)}>\n                <input\n                  type="checkbox"\n                  checked={selectedReasons.includes(reason)}\n                  onChange={() => toggleReason(reason)}\n                />\n                <span>{reason}</span>\n              </label>\n            ))}\n          </div>\n          <label className={styles.researchNote}>\n            研究备注（可选）\n            <textarea\n              value={researchNote}\n              onChange={(event) => setResearchNote(event.target.value)}\n              placeholder="例如：预测市场可能成为金融科技的新基础设施，重点观察融资、牌照和监管窗口。"\n            />\n          </label>\n        </section>\n\n        <section className={styles.section}>\n          <div className={styles.sectionHeading}>\n            <div>\n              <p>04 / ADMIN COMMIT</p>\n              <h3>管理员同步</h3>''',
    )


def patch_capture_drawer_styles() -> None:
    path = "components/intelligence-tracking-capture-controls.module.css"
    append_once(
        path,
        ".securityNote {",
        '''.reasonGrid {\n  display: grid;\n  grid-template-columns: repeat(2, minmax(0, 1fr));\n  gap: 8px;\n}\n\n.reasonGrid label {\n  display: flex;\n  align-items: center;\n  gap: 8px;\n  min-height: 38px;\n  padding: 8px 10px;\n  border: 1px solid var(--border-soft);\n  background: var(--surface-2);\n  color: var(--muted);\n  font-size: 12px;\n  cursor: pointer;\n}\n\n.reasonGrid label[data-selected="true"] {\n  border-color: var(--green);\n  background: color-mix(in srgb, var(--green) 10%, var(--surface));\n  color: var(--green-bright);\n}\n\n.reasonGrid input {\n  accent-color: var(--green-bright);\n}\n\n.researchNote {\n  display: grid;\n  gap: 7px;\n  margin-top: 14px;\n  color: var(--muted);\n  font-size: 12px;\n}\n\n.researchNote textarea {\n  width: 100%;\n  min-height: 86px;\n  padding: 10px 11px;\n  resize: vertical;\n  border: 1px solid var(--border);\n  background: var(--bg);\n  color: var(--text);\n  font: inherit;\n  line-height: 1.55;\n}''',
    )
    replace_once(
        path,
        '''  .trackGrid {\n    grid-template-columns: 1fr;\n  }''',
        '''  .trackGrid,\n  .reasonGrid {\n    grid-template-columns: 1fr;\n  }''',
    )


def patch_capture_inbox() -> None:
    path = "components/tracking-capture-inbox.tsx"
    replace_once(
        path,
        '''import { ExternalLink, Inbox, RefreshCw } from "lucide-react";\nimport { useEffect, useMemo, useState } from "react";''',
        '''import { BookOpen, ExternalLink, Inbox, RefreshCw } from "lucide-react";\nimport Link from "next/link";\nimport { useEffect, useMemo, useState } from "react";''',
    )
    replace_once(
        path,
        '''import { base64ToText } from "@/lib/github-commit";''',
        '''import { base64ToText } from "@/lib/github-commit";\nimport { trackingEntityResearchHref } from "@/lib/tracking-entity-route";''',
    )
    replace_once(
        path,
        '''        <button type="button" className={styles.reload} disabled={loading} onClick={reload}>\n          <RefreshCw className={loading ? styles.spinning : undefined} size={15} />\n          重新载入\n        </button>''',
        '''        <div className={styles.headerActions}>\n          <Link href="/tracking/entities" className={styles.libraryLink}>\n            <BookOpen size={15} />追踪对象研究库\n          </Link>\n          <button type="button" className={styles.reload} disabled={loading} onClick={reload}>\n            <RefreshCw className={loading ? styles.spinning : undefined} size={15} />\n            重新载入\n          </button>\n        </div>''',
    )
    replace_once(
        path,
        '''            </dl>\n            <div className={styles.source}>''',
        '''            </dl>\n            {record.reasons.length || record.note ? (\n              <div className={styles.researchMeta}>\n                {record.reasons.length ? (\n                  <div>{record.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>\n                ) : null}\n                {record.note ? <p>{record.note}</p> : null}\n              </div>\n            ) : null}\n            <div className={styles.source}>''',
    )
    replace_once(
        path,
        '''              <a href={record.source.url} target="_blank" rel="noreferrer">\n                原文 <ExternalLink size={13} />\n              </a>''',
        '''              <div className={styles.sourceActions}>\n                <Link href={trackingEntityResearchHref(record.entityType, record.canonicalName)}>\n                  研究页 <BookOpen size={13} />\n                </Link>\n                <a href={record.source.url} target="_blank" rel="noreferrer">\n                  原文 <ExternalLink size={13} />\n                </a>\n              </div>''',
    )


def patch_capture_inbox_styles() -> None:
    path = "components/tracking-capture-inbox.module.css"
    append_once(
        path,
        ".reload {",
        '''.headerActions {\n  display: flex;\n  flex-wrap: wrap;\n  justify-content: flex-end;\n  gap: 8px;\n}\n\n.libraryLink {\n  display: inline-flex;\n  align-items: center;\n  gap: 6px;\n  min-height: 38px;\n  padding: 8px 12px;\n  border: 1px solid var(--green);\n  color: var(--green-bright);\n  font-size: 12px;\n  text-decoration: none;\n  white-space: nowrap;\n}''',
    )
    append_once(
        path,
        ".source {",
        '''.researchMeta {\n  display: grid;\n  gap: 8px;\n  margin: 12px 0;\n  padding: 11px;\n  border-left: 2px solid var(--ochre);\n  background: color-mix(in srgb, var(--ochre) 5%, transparent);\n}\n\n.researchMeta > div {\n  display: flex;\n  flex-wrap: wrap;\n  gap: 5px;\n}\n\n.researchMeta span {\n  border: 1px solid var(--border-soft);\n  padding: 3px 6px;\n  color: var(--muted);\n  font-size: 10px;\n}\n\n.researchMeta p {\n  margin: 0;\n  color: var(--muted);\n  font-size: 11px;\n  line-height: 1.6;\n}''',
    )
    append_once(
        path,
        ".empty {",
        '''.sourceActions {\n  display: flex;\n  flex-direction: column;\n  align-items: flex-end;\n  gap: 8px;\n}\n\n.sourceActions a {\n  display: inline-flex;\n  align-items: center;\n  gap: 4px;\n  color: var(--green-bright);\n  font-size: 11px;\n  text-decoration: none;\n  white-space: nowrap;\n}''',
    )


def patch_capture_tests() -> None:
    path = "tests/tracking-capture.test.ts"
    replace_once(
        path,
        '''    capturedAt: "2026-08-05T04:00:00Z",\n    capturedBy: "VCIQ",\n  });''',
        '''    capturedAt: "2026-08-05T04:00:00Z",\n    capturedBy: "VCIQ",\n    reasons: ["商业模式创新", "监管变化"],\n    note: "重点观察牌照、融资和市场竞争。",\n  });''',
    )
    replace_once(
        path,
        '''  assert.equal(result.records[0].status, "applied");\n});''',
        '''  assert.equal(result.records[0].status, "applied");\n  assert.deepEqual(result.records[0].reasons, ["商业模式创新", "监管变化"]);\n  assert.equal(result.records[0].note, "重点观察牌照、融资和市场竞争。");\n});''',
    )
    append_once(
        path,
        'test("company suffix normalization cannot create an empty entity", () => {',
        '''test("legacy inbox records receive empty research intent fields", () => {\n  const inbox = normalizeTrackingCaptureInbox({\n    records: [\n      {\n        id: "legacy",\n        entityType: "company",\n        canonicalName: "Polymarket",\n        trackSlugs: ["ai-agi"],\n        source,\n        capturedAt: "2026-08-05T04:00:00Z",\n        status: "applied",\n      },\n    ],\n  });\n  assert.deepEqual(inbox.records[0].reasons, []);\n  assert.equal(inbox.records[0].note, "");\n});''',
    )


def main() -> int:
    patch_capture_model()
    patch_capture_drawer()
    patch_capture_drawer_styles()
    patch_capture_inbox()
    patch_capture_inbox_styles()
    patch_capture_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
