from pathlib import Path

path = Path("components/tracking-entity-resolution-review.tsx")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        'import { useEffect, useMemo, useState } from "react";',
        'import { useMemo, useState } from "react";',
    ),
    (
        'type StatusKind = "neutral" | "success" | "error";\n',
        'type StatusKind = "neutral" | "success" | "error";\n'
        'type ResolutionDraft = {\n'
        '  entityType: EntityResolutionEntityType;\n'
        '  canonicalName: string;\n'
        '  targetId: string;\n'
        '  note: string;\n'
        '};\n',
    ),
    (
        'function defaultTargetId(type: EntityResolutionEntityType, canonicalName: string) {\n'
        '  const key = normalizeEntityResolutionIdentity(canonicalName);\n'
        '  if (!key) return "";\n'
        '  return type === "company" ? `company-candidate:${key}` : `${type}:${key}`;\n'
        '}\n',
        'function defaultTargetId(type: EntityResolutionEntityType, canonicalName: string) {\n'
        '  const key = normalizeEntityResolutionIdentity(canonicalName);\n'
        '  if (!key) return "";\n'
        '  return type === "company" ? `company-candidate:${key}` : `${type}:${key}`;\n'
        '}\n\n'
        'function defaultResolutionDraft(\n'
        '  item: ReviewItem,\n'
        '  manifest: EntityResolutionManifest,\n'
        '): ResolutionDraft {\n'
        '  const decision = manifest.decisions[item.resolution.decisionKey];\n'
        '  return {\n'
        '    entityType: decision?.entityType ?? item.resolution.entityType,\n'
        '    canonicalName:\n'
        '      decision?.canonicalName ??\n'
        '      item.record.rawSelection ??\n'
        '      item.record.canonicalName,\n'
        '    targetId: decision?.targetId ?? "",\n'
        '    note: decision?.note ?? item.resolution.reason,\n'
        '  };\n'
        '}\n',
    ),
    (
        '  const [selectedKey, setSelectedKey] = useState("");\n'
        '  const [entityType, setEntityType] = useState<EntityResolutionEntityType>("person");\n'
        '  const [canonicalName, setCanonicalName] = useState("");\n'
        '  const [targetId, setTargetId] = useState("");\n'
        '  const [note, setNote] = useState("");\n',
        '  const [selectedKey, setSelectedKey] = useState("");\n'
        '  const [drafts, setDrafts] = useState<Record<string, ResolutionDraft>>({});\n',
    ),
    (
        '  const items = useMemo(() => buildReviewItems(inbox, manifest), [inbox, manifest]);\n'
        '  const selected = useMemo(\n'
        '    () => items.find((item) => item.resolution.decisionKey === selectedKey) ?? items[0],\n'
        '    [items, selectedKey],\n'
        '  );\n\n'
        '  useEffect(() => {\n'
        '    if (!selected) return;\n'
        '    const decision = manifest.decisions[selected.resolution.decisionKey];\n'
        '    setSelectedKey(selected.resolution.decisionKey);\n'
        '    setEntityType(decision?.entityType ?? selected.resolution.entityType);\n'
        '    setCanonicalName(decision?.canonicalName ?? selected.record.rawSelection ?? selected.record.canonicalName);\n'
        '    setTargetId(decision?.targetId ?? "");\n'
        '    setNote(decision?.note ?? selected.resolution.reason);\n'
        '  }, [manifest.decisions, selected]);\n',
        '  const items = useMemo(() => buildReviewItems(inbox, manifest), [inbox, manifest]);\n'
        '  const activeKey = items.some(\n'
        '    (item) => item.resolution.decisionKey === selectedKey,\n'
        '  )\n'
        '    ? selectedKey\n'
        '    : items[0]?.resolution.decisionKey ?? "";\n'
        '  const selected = useMemo(\n'
        '    () => items.find((item) => item.resolution.decisionKey === activeKey),\n'
        '    [activeKey, items],\n'
        '  );\n'
        '  const draft = selected\n'
        '    ? drafts[activeKey] ?? defaultResolutionDraft(selected, manifest)\n'
        '    : undefined;\n\n'
        '  function updateDraft(patch: Partial<ResolutionDraft>) {\n'
        '    if (!selected) return;\n'
        '    const key = selected.resolution.decisionKey;\n'
        '    setDrafts((current) => ({\n'
        '      ...current,\n'
        '      [key]: {\n'
        '        ...(current[key] ?? defaultResolutionDraft(selected, manifest)),\n'
        '        ...patch,\n'
        '      },\n'
        '    }));\n'
        '  }\n',
    ),
    (
        '      setManifest(nextManifest);\n      setInbox(nextInbox);\n',
        '      setManifest(nextManifest);\n      setInbox(nextInbox);\n      setDrafts({});\n',
    ),
    (
        '  async function saveDecision(nextStatus: EntityResolutionStatus) {\n'
        '    if (!selected) return;\n'
        '    const cleanToken = token.trim();\n'
        '    const cleanName = canonicalName.normalize("NFKC").replace(/\\s+/gu, " ").trim();\n',
        '  async function saveDecision(nextStatus: EntityResolutionStatus) {\n'
        '    if (!selected || !draft) return;\n'
        '    const { entityType, canonicalName, targetId, note } = draft;\n'
        '    const cleanToken = token.trim();\n'
        '    const cleanName = canonicalName.normalize("NFKC").replace(/\\s+/gu, " ").trim();\n',
    ),
    (
        '      setManifest(nextManifest);\n'
        '      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);\n',
        '      setManifest(nextManifest);\n'
        '      setDrafts((current) => {\n'
        '        const next = { ...current };\n'
        '        delete next[selected.resolution.decisionKey];\n'
        '        return next;\n'
        '      });\n'
        '      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);\n',
    ),
    (
        '      {selected ? (\n',
        '      {selected && draft ? (\n',
    ),
    (
        '                  onChange={(event) => setEntityType(event.target.value as EntityResolutionEntityType)}\n'
        '                  value={entityType}\n',
        '                  onChange={(event) =>\n'
        '                    updateDraft({\n'
        '                      entityType: event.target.value as EntityResolutionEntityType,\n'
        '                    })\n'
        '                  }\n'
        '                  value={draft.entityType}\n',
    ),
    (
        '                  onChange={(event) => setCanonicalName(event.target.value)}\n'
        '                  value={canonicalName}\n',
        '                  onChange={(event) =>\n'
        '                    updateDraft({ canonicalName: event.target.value })\n'
        '                  }\n'
        '                  value={draft.canonicalName}\n',
    ),
    (
        '                  onChange={(event) => setTargetId(event.target.value)}\n'
        '                  placeholder={defaultTargetId(entityType, canonicalName)}\n'
        '                  value={targetId}\n',
        '                  onChange={(event) =>\n'
        '                    updateDraft({ targetId: event.target.value })\n'
        '                  }\n'
        '                  placeholder={defaultTargetId(\n'
        '                    draft.entityType,\n'
        '                    draft.canonicalName,\n'
        '                  )}\n'
        '                  value={draft.targetId}\n',
    ),
    (
        '                  onChange={(event) => setNote(event.target.value)}\n'
        '                  value={note}\n',
        '                  onChange={(event) => updateDraft({ note: event.target.value })}\n'
        '                  value={draft.note}\n',
    ),
]

for old, new in replacements:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match, found {count}: {old[:80]!r}")
    text = text.replace(old, new)

path.write_text(text, encoding="utf-8")
