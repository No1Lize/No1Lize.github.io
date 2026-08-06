"use client";

import rawInbox from "@/config/tracking_capture_inbox.json";
import { Check, RefreshCw, ShieldAlert, ShieldCheck, X } from "lucide-react";
import { useMemo, useState } from "react";
import {
  entityResolutionDecisionManifest,
  normalizeEntityResolutionIdentity,
  normalizeEntityResolutionManifest,
  resolveTrackingEntity,
  type EntityResolutionDecision,
  type EntityResolutionEntityType,
  type EntityResolutionManifest,
  type EntityResolutionStatus,
  type TrackingEntityResolution,
} from "@/lib/entity-resolution";
import {
  TRACKING_ADMIN_TOKEN_SESSION_KEY,
  normalizeTrackingCaptureInbox,
  type TrackingCaptureRecord,
} from "@/lib/tracking-capture";
import {
  TRACKING_BRANCH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import styles from "./tracking-entity-resolution-review.module.css";

const API_ROOT = "https://api.github.com";
const DECISIONS_PATH = "config/entity_resolution_decisions.json";
const INBOX_PATH = "config/tracking_capture_inbox.json";

type GithubFile = { sha: string; content: string };
type ReviewItem = { record: TrackingCaptureRecord; resolution: TrackingEntityResolution };
type StatusKind = "neutral" | "success" | "error";
type ResolutionDraft = {
  entityType: EntityResolutionEntityType;
  canonicalName: string;
  targetId: string;
  note: string;
};

const TYPE_LABELS: Record<EntityResolutionEntityType, string> = {
  company: "公司",
  person: "人物",
  topic: "技术／主题",
};

function encodeBase64(value: string) {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...Array.from(bytes.subarray(index, index + 8192)));
  }
  return btoa(binary);
}

function decodeBase64(value: string) {
  const binary = atob(value.replace(/\n/gu, ""));
  return new TextDecoder().decode(
    Uint8Array.from(binary, (character) => character.charCodeAt(0)),
  );
}

async function githubJson<T>(url: string, token: string, init?: RequestInit) {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.headers ?? {}),
    },
  });
  const raw = await response.text();
  let payload: Record<string, unknown> = {};
  try {
    payload = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
  } catch {
    payload = {};
  }
  if (!response.ok) {
    const message = typeof payload.message === "string" ? payload.message : raw;
    throw new Error(`${response.status} ${message || "GitHub API 请求失败"}`);
  }
  return payload as T;
}

function currentToken() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(TRACKING_ADMIN_TOKEN_SESSION_KEY)?.trim() ?? "";
}

function buildReviewItems(
  inboxValue: unknown,
  manifest: EntityResolutionManifest,
): ReviewItem[] {
  return normalizeTrackingCaptureInbox(inboxValue).records
    .map((record) => {
      const requestedType = record.resolution?.requestedType ?? record.entityType;
      const name = record.rawSelection || record.canonicalName;
      return {
        record,
        resolution: resolveTrackingEntity({
          requestedType,
          name,
          source: record.source,
          manifest,
        }),
      };
    })
    .filter((item) => item.resolution.status === "review")
    .sort((left, right) =>
      right.record.capturedAt.localeCompare(left.record.capturedAt) ||
      left.record.canonicalName.localeCompare(right.record.canonicalName, "zh-CN"),
    );
}

function orderedManifest(manifest: EntityResolutionManifest) {
  return {
    schemaVersion: 1,
    generatedAt: manifest.generatedAt,
    decisions: Object.fromEntries(
      Object.entries(manifest.decisions).sort(([left], [right]) =>
        left.localeCompare(right, "zh-CN"),
      ),
    ),
  };
}

function defaultTargetId(type: EntityResolutionEntityType, canonicalName: string) {
  const key = normalizeEntityResolutionIdentity(canonicalName);
  if (!key) return "";
  return type === "company" ? `company-candidate:${key}` : `${type}:${key}`;
}

function defaultResolutionDraft(
  item: ReviewItem,
  manifest: EntityResolutionManifest,
): ResolutionDraft {
  const decision = manifest.decisions[item.resolution.decisionKey];
  return {
    entityType: decision?.entityType ?? item.resolution.entityType,
    canonicalName:
      decision?.canonicalName ??
      item.record.rawSelection ??
      item.record.canonicalName,
    targetId: decision?.targetId ?? "",
    note: decision?.note ?? item.resolution.reason,
  };
}

export function TrackingEntityResolutionReview() {
  const [manifest, setManifest] = useState(() => entityResolutionDecisionManifest);
  const [inbox, setInbox] = useState<unknown>(rawInbox);
  const [selectedKey, setSelectedKey] = useState("");
  const [drafts, setDrafts] = useState<Record<string, ResolutionDraft>>({});
  const [token, setToken] = useState(currentToken);
  const [busy, setBusy] = useState(false);
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [status, setStatus] = useState(
    "低置信实体不会写入公司候选池。管理员决定会形成版本化解析记忆。",
  );

  const items = useMemo(() => buildReviewItems(inbox, manifest), [inbox, manifest]);
  const activeKey = items.some(
    (item) => item.resolution.decisionKey === selectedKey,
  )
    ? selectedKey
    : items[0]?.resolution.decisionKey ?? "";
  const selected = useMemo(
    () => items.find((item) => item.resolution.decisionKey === activeKey),
    [activeKey, items],
  );
  const draft = selected
    ? drafts[activeKey] ?? defaultResolutionDraft(selected, manifest)
    : undefined;

  function updateDraft(patch: Partial<ResolutionDraft>) {
    if (!selected) return;
    const key = selected.resolution.decisionKey;
    setDrafts((current) => ({
      ...current,
      [key]: {
        ...(current[key] ?? defaultResolutionDraft(selected, manifest)),
        ...patch,
      },
    }));
  }

  async function loadLatest(providedToken?: string) {
    const cleanToken = (providedToken ?? token).trim();
    if (!cleanToken) {
      setStatusKind("error");
      setStatus("请先填写仓库管理员 Fine-grained Token。");
      return;
    }
    setBusy(true);
    setStatusKind("neutral");
    setStatus("正在读取 main 上的最新解析决定与采集箱……");
    try {
      const user = await githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken);
      if (user.login.toLocaleLowerCase("en-US") !== TRACKING_OWNER.toLocaleLowerCase("en-US")) {
        throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}`);
      }
      const [decisionFile, inboxFile] = await Promise.all([
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISIONS_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${INBOX_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
      ]);
      const nextManifest = normalizeEntityResolutionManifest(
        JSON.parse(decodeBase64(decisionFile.content)),
      );
      const nextInbox = JSON.parse(decodeBase64(inboxFile.content));
      setToken(cleanToken);
      setManifest(nextManifest);
      setInbox(nextInbox);
      setDrafts({});
      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);
      setStatusKind("success");
      setStatus(`已载入最新解析队列，共 ${buildReviewItems(nextInbox, nextManifest).length} 项待核。`);
    } catch (error) {
      setStatusKind("error");
      setStatus(`载入失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function saveDecision(nextStatus: EntityResolutionStatus) {
    if (!selected || !draft) return;
    const { entityType, canonicalName, targetId, note } = draft;
    const cleanToken = token.trim();
    const cleanName = canonicalName.normalize("NFKC").replace(/\s+/gu, " ").trim();
    if (!cleanToken) {
      setStatusKind("error");
      setStatus("请先填写仓库管理员 Fine-grained Token。");
      return;
    }
    if (!cleanName) {
      setStatusKind("error");
      setStatus("规范实体名称不能为空。");
      return;
    }
    if (nextStatus !== "resolved" && !note.trim()) {
      setStatusKind("error");
      setStatus("保留待核或拒绝实体时必须填写原因。");
      return;
    }

    setBusy(true);
    setStatusKind("neutral");
    setStatus(`正在保存“${selected.record.rawSelection || selected.record.canonicalName}”的解析决定……`);
    try {
      let committed = false;
      let nextManifest = manifest;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const [user, latestFile] = await Promise.all([
          githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken),
          githubJson<GithubFile>(
            `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISIONS_PATH}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`,
            cleanToken,
          ),
        ]);
        if (user.login.toLocaleLowerCase("en-US") !== TRACKING_OWNER.toLocaleLowerCase("en-US")) {
          throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}`);
        }
        const latest = normalizeEntityResolutionManifest(
          JSON.parse(decodeBase64(latestFile.content)),
        );
        const now = new Date().toISOString();
        const decision: EntityResolutionDecision = {
          status: nextStatus,
          requestedType: selected.resolution.requestedType,
          entityType,
          canonicalName: cleanName,
          targetId:
            nextStatus === "resolved"
              ? targetId.trim() || defaultTargetId(entityType, cleanName)
              : "",
          aliases: Array.from(
            new Set([
              selected.record.rawSelection,
              selected.record.canonicalName,
              cleanName,
            ].filter(Boolean)),
          ),
          confidence: nextStatus === "review" ? "low" : "verified",
          note: note.trim(),
          reviewedBy: user.login,
          reviewedAt: now,
        };
        nextManifest = {
          schemaVersion: 1,
          generatedAt: now,
          decisions: {
            ...latest.decisions,
            [selected.resolution.decisionKey]: decision,
          },
        };
        try {
          await githubJson(
            `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISIONS_PATH}`,
            cleanToken,
            {
              method: "PUT",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                message: `resolve: ${nextStatus} entity ${cleanName}`,
                content: encodeBase64(`${JSON.stringify(orderedManifest(nextManifest), null, 2)}\n`),
                sha: latestFile.sha,
                branch: TRACKING_BRANCH,
              }),
            },
          );
          committed = true;
          break;
        } catch (error) {
          if (attempt === 0 && error instanceof Error && /^409\b|^422\b/u.test(error.message)) {
            continue;
          }
          throw error;
        }
      }
      if (!committed) throw new Error("解析决定提交未完成。");
      setManifest(nextManifest);
      setDrafts((current) => {
        const next = { ...current };
        delete next[selected.resolution.decisionKey];
        return next;
      });
      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);
      setStatusKind("success");
      setStatus(
        nextStatus === "resolved"
          ? "解析决定已提交。后台会重整追踪配置、采集记录和公司候选池。"
          : nextStatus === "rejected"
            ? "拒绝决定已提交；该对象不会进入追踪配置或候选池。"
            : "已保留在待核队列，不会进入公司候选池。",
      );
    } catch (error) {
      setStatusKind("error");
      setStatus(`保存失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.section} id="entity-resolution-review">
      <header className={styles.header}>
        <div>
          <p className="eyebrow">ENTITY RESOLUTION CENTER</p>
          <h2>实体解析与消歧中心</h2>
          <p>
            统一审核公司、人物和技术主题。低置信对象只进入此队列；人工决定会被后续采集、候选生成和研究图谱复用。
          </p>
        </div>
        <div className={styles.metric}>
          <span>待核实体</span>
          <strong>{items.length}</strong>
        </div>
      </header>

      <div className={styles.toolbar}>
        <label>
          <span>GitHub Token</span>
          <input
            autoComplete="off"
            disabled={busy}
            onChange={(event) => setToken(event.target.value)}
            placeholder="仅保存在当前标签页"
            type="password"
            value={token}
          />
        </label>
        <button disabled={busy} onClick={() => void loadLatest()} type="button">
          <RefreshCw size={14} />重新载入
        </button>
      </div>
      <p className={styles.status} data-kind={statusKind}>{status}</p>

      {selected && draft ? (
        <div className={styles.workspace}>
          <nav className={styles.list} aria-label="待核实体列表">
            {items.map((item) => (
              <button
                data-active={item.resolution.decisionKey === selected.resolution.decisionKey}
                key={`${item.record.id}-${item.resolution.decisionKey}`}
                onClick={() => setSelectedKey(item.resolution.decisionKey)}
                type="button"
              >
                <strong>{item.record.rawSelection || item.record.canonicalName}</strong>
                <span>{TYPE_LABELS[item.resolution.requestedType]} → 建议 {TYPE_LABELS[item.resolution.entityType]}</span>
                <small>{item.resolution.reason}</small>
              </button>
            ))}
          </nav>

          <article className={styles.detail}>
            <header>
              <div>
                <p className="section-index">REVIEW CONTEXT</p>
                <h3>{selected.record.rawSelection || selected.record.canonicalName}</h3>
              </div>
              <span><ShieldAlert size={14} />{selected.resolution.confidence}</span>
            </header>
            <a href={selected.record.source.url} rel="noreferrer" target="_blank">
              {selected.record.source.title}
            </a>
            <blockquote>{selected.record.source.summary || "该采集记录没有摘要。"}</blockquote>

            <div className={styles.form}>
              <label>
                <span>规范类型</span>
                <select
                  disabled={busy}
                  onChange={(event) =>
                    updateDraft({
                      entityType: event.target.value as EntityResolutionEntityType,
                    })
                  }
                  value={draft.entityType}
                >
                  <option value="company">公司</option>
                  <option value="person">人物</option>
                  <option value="topic">技术／主题</option>
                </select>
              </label>
              <label>
                <span>规范名称</span>
                <input
                  disabled={busy}
                  maxLength={160}
                  onChange={(event) =>
                    updateDraft({ canonicalName: event.target.value })
                  }
                  value={draft.canonicalName}
                />
              </label>
              <label className={styles.wide}>
                <span>规范实体 ID（可选）</span>
                <input
                  disabled={busy}
                  maxLength={240}
                  onChange={(event) =>
                    updateDraft({ targetId: event.target.value })
                  }
                  placeholder={defaultTargetId(
                    draft.entityType,
                    draft.canonicalName,
                  )}
                  value={draft.targetId}
                />
              </label>
              <label className={styles.wide}>
                <span>审核说明</span>
                <textarea
                  disabled={busy}
                  maxLength={600}
                  onChange={(event) => updateDraft({ note: event.target.value })}
                  value={draft.note}
                />
              </label>
            </div>

            <div className={styles.actions}>
              <button className={styles.resolve} disabled={busy} onClick={() => void saveDecision("resolved")} type="button">
                <Check size={14} />确认解析
              </button>
              <button disabled={busy} onClick={() => void saveDecision("review")} type="button">
                <ShieldCheck size={14} />保留待核
              </button>
              <button className={styles.reject} disabled={busy} onClick={() => void saveDecision("rejected")} type="button">
                <X size={14} />拒绝实体
              </button>
            </div>
          </article>
        </div>
      ) : (
        <div className={styles.empty}>
          <ShieldCheck size={22} />
          <strong>当前没有待核实体</strong>
          <p>新采集的低置信对象会自动进入这里。</p>
        </div>
      )}
    </section>
  );
}
