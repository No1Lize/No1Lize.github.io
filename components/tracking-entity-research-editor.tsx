"use client";

import { RefreshCw, Save, ShieldCheck, Star } from "lucide-react";
import { useState } from "react";
import {
  TrackingEntityRecordConflictError,
  commitTrackingEntityRecordManifest,
  fetchTrackingEntityRecordRepositoryState,
} from "@/lib/tracking-entity-records-github";
import {
  TRACKING_ENTITY_RECORDS_CHANGED_EVENT,
  TRACKING_RESEARCH_REASON_OPTIONS,
  trackingEntityPriorityLabel,
  trackingEntityPriorityStars,
  updateTrackingEntityRecord,
  type TrackingEntityResearchRecord,
} from "@/lib/tracking-entity-records";
import {
  TRACKING_ADMIN_TOKEN_SESSION_KEY,
  type TrackingCaptureEntityType,
} from "@/lib/tracking-capture";
import styles from "./tracking-entity-research-editor.module.css";

type StatusKind = "neutral" | "success" | "error";

function initialToken() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(TRACKING_ADMIN_TOKEN_SESSION_KEY) ?? "";
}

function displayTime(value: string) {
  if (!value) return "";
  try {
    return new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Taipei",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export function TrackingEntityResearchEditor({
  entityId,
  entityType,
  entityName,
  initialRecord,
}: {
  entityId: string;
  entityType: TrackingCaptureEntityType;
  entityName: string;
  initialRecord?: TrackingEntityResearchRecord;
}) {
  const [record, setRecord] = useState<TrackingEntityResearchRecord | undefined>(
    initialRecord,
  );
  const [priority, setPriority] = useState(initialRecord?.priority ?? 0);
  const [reasons, setReasons] = useState<string[]>(initialRecord?.reasons ?? []);
  const [thesis, setThesis] = useState(initialRecord?.thesis ?? "");
  const [newNote, setNewNote] = useState("");
  const [token, setToken] = useState(initialToken);
  const [busy, setBusy] = useState(false);
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [status, setStatus] = useState(
    "设置关注等级、研究判断和追加式笔记。保存后会触发 Pages 自动重建。",
  );

  function applyRecord(next: TrackingEntityResearchRecord | undefined) {
    setRecord(next);
    setPriority(next?.priority ?? 0);
    setReasons(next?.reasons ?? []);
    setThesis(next?.thesis ?? "");
  }

  async function reload() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setStatusKind("error");
      setStatus("请先填写网站追踪管理使用的 GitHub Token。");
      return;
    }
    setBusy(true);
    setStatusKind("neutral");
    setStatus("正在读取 main 上的最新研究记录……");
    try {
      const state = await fetchTrackingEntityRecordRepositoryState(cleanToken);
      const next = state.manifest.records[entityId];
      applyRecord(next);
      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);
      setStatusKind("success");
      setStatus(next ? "已载入最新研究记录。" : "当前对象尚未建立独立研究记录。");
    } catch (error) {
      setStatusKind("error");
      setStatus(`载入失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  async function save() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setStatusKind("error");
      setStatus("请先填写网站追踪管理使用的 GitHub Token。");
      return;
    }
    if (!priority && !reasons.length && !thesis.trim() && !newNote.trim()) {
      setStatusKind("error");
      setStatus("至少设置关注等级、关注原因、研究判断或新增一条笔记。");
      return;
    }

    setBusy(true);
    setStatusKind("neutral");
    setStatus(`正在保存“${entityName}”的研究记录……`);
    try {
      let commitSha = "";
      let savedRecord: TrackingEntityResearchRecord | undefined;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const state = await fetchTrackingEntityRecordRepositoryState(cleanToken);
        const updatedAt = new Date().toISOString();
        const nextManifest = updateTrackingEntityRecord(state.manifest, {
          entityId,
          entityType,
          canonicalName: entityName,
          priority,
          reasons,
          thesis,
          noteBody: newNote,
          updatedAt,
          updatedBy: state.username,
        });
        try {
          commitSha = await commitTrackingEntityRecordManifest(
            cleanToken,
            state,
            nextManifest,
            entityName,
          );
          savedRecord = nextManifest.records[entityId];
          break;
        } catch (error) {
          if (error instanceof TrackingEntityRecordConflictError && attempt === 0) {
            continue;
          }
          throw error;
        }
      }
      if (!commitSha || !savedRecord) {
        throw new Error("研究记录提交未完成。");
      }
      window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);
      setRecord(savedRecord);
      setPriority(savedRecord.priority);
      setReasons(savedRecord.reasons);
      setThesis(savedRecord.thesis);
      setNewNote("");
      window.dispatchEvent(
        new CustomEvent(TRACKING_ENTITY_RECORDS_CHANGED_EVENT, {
          detail: { entityId, commitSha },
        }),
      );
      setStatusKind("success");
      setStatus(
        `研究记录已提交（${commitSha.slice(0, 8)}）。生产页面将在 Pages 部署完成后更新。`,
      );
    } catch (error) {
      setStatusKind("error");
      setStatus(`保存失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.editor} aria-labelledby="tracking-research-editor-title">
      <header>
        <div>
          <p className="section-index">ANALYST WORKSPACE</p>
          <h2 id="tracking-research-editor-title">研究维护</h2>
        </div>
        <span data-priority={priority}>
          <Star size={14} aria-hidden="true" />
          {trackingEntityPriorityLabel(priority)}
        </span>
      </header>

      <div className={styles.priority}>
        <strong>关注等级</strong>
        <div role="radiogroup" aria-label="关注等级">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              aria-checked={priority === value}
              data-active={priority === value}
              disabled={busy}
              key={value}
              onClick={() => setPriority(priority === value ? 0 : value)}
              role="radio"
              type="button"
              title={`${trackingEntityPriorityStars(value)} ${trackingEntityPriorityLabel(value)}`}
            >
              {value}
            </button>
          ))}
        </div>
        <small>{trackingEntityPriorityStars(priority)} · {trackingEntityPriorityLabel(priority)}</small>
      </div>

      <fieldset className={styles.reasons}>
        <legend>结构化关注原因</legend>
        {TRACKING_RESEARCH_REASON_OPTIONS.map((reason) => (
          <label key={reason}>
            <input
              checked={reasons.includes(reason)}
              disabled={busy}
              onChange={(event) =>
                setReasons((current) =>
                  event.target.checked
                    ? [...current, reason]
                    : current.filter((item) => item !== reason),
                )
              }
              type="checkbox"
            />
            <span>{reason}</span>
          </label>
        ))}
      </fieldset>

      <label className={styles.field}>
        <span>当前研究判断</span>
        <textarea
          disabled={busy}
          maxLength={2000}
          onChange={(event) => setThesis(event.target.value)}
          placeholder="例如：预测市场可能成为金融信息基础设施的一部分，核心变量是监管、流动性与市场扩张。"
          value={thesis}
        />
      </label>

      <label className={styles.field}>
        <span>追加研究笔记</span>
        <textarea
          disabled={busy}
          maxLength={4000}
          onChange={(event) => setNewNote(event.target.value)}
          placeholder="新增笔记采用追加式保存，保留时间和管理员账号。"
          value={newNote}
        />
      </label>

      <label className={styles.token}>
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

      <div className={styles.actions}>
        <button disabled={busy} onClick={() => void reload()} type="button">
          <RefreshCw size={14} aria-hidden="true" />重新载入
        </button>
        <button className={styles.save} disabled={busy} onClick={() => void save()} type="button">
          <Save size={14} aria-hidden="true" />保存研究记录
        </button>
      </div>

      <p className={styles.status} data-kind={statusKind}>{status}</p>
      <p className={styles.security}>
        <ShieldCheck size={14} aria-hidden="true" />
        Token 只保存在当前标签页；提交记录保留 Git 历史、管理员和时间。
      </p>

      {record?.notes.length ? (
        <div className={styles.history}>
          <h3>最近研究笔记</h3>
          {record.notes.slice(0, 8).map((note) => (
            <article key={note.id}>
              <p>{note.body}</p>
              <span>{displayTime(note.createdAt)} · {note.createdBy || "管理员"}</span>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
