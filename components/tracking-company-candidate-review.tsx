"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";
import {
  ArrowUpRight,
  Check,
  GitMerge,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";
import rawDecisions from "@/config/company_candidate_decisions.json";
import {
  companyCandidateSnapshot,
  normalizeCompanyCandidateSnapshot,
  type CompanyCandidateSnapshot,
  type CompanyCandidateStatus,
} from "@/lib/company-candidate-data";
import {
  applyCompanyCandidateDecisions,
  companyCandidateEvidenceFingerprint,
  countCompanyCandidateReviews,
  decisionForCompanyCandidate,
  normalizeCompanyCandidateDecisionManifest,
  setCompanyCandidateDecision,
  validateCompanyCandidateDecision,
  type CompanyCandidateDecisionManifest,
  type ReviewedCompanyCandidate,
} from "@/lib/company-candidate-review";
import {
  TRACKING_BRANCH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import styles from "./tracking-company-candidate-review.module.css";

const API_ROOT = "https://api.github.com";
const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
const CANDIDATE_PATH = "public/data/company_candidates.json";
const DECISION_PATH = "config/company_candidate_decisions.json";
const FILTERS: CompanyCandidateStatus[] = [
  "pending",
  "accepted",
  "rejected",
  "merged",
];

const STATUS_LABELS: Record<CompanyCandidateStatus, string> = {
  pending: "待审核",
  accepted: "已通过",
  rejected: "已拒绝",
  merged: "已合并",
};

const emptyMountSubscribe = () => () => {};

type GithubFile = {
  sha: string;
  content: string;
};

type StatusKind = "neutral" | "success" | "error";

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
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
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

function orderedManifest(manifest: CompanyCandidateDecisionManifest) {
  return {
    schemaVersion: Math.max(1, manifest.schemaVersion || 1),
    decisions: Object.fromEntries(
      Object.entries(manifest.decisions).sort(([left], [right]) =>
        left.localeCompare(right, "zh-CN"),
      ),
    ),
  };
}

function displayTime(value: string) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function currentToken() {
  return window.sessionStorage.getItem(TOKEN_SESSION_KEY)?.trim() ?? "";
}

function sourceHost(url: string) {
  try {
    return new URL(url).hostname;
  } catch {
    return "公开来源";
  }
}

function ensureShortcutHost() {
  const input = document.querySelector<HTMLInputElement>("#github-token");
  const row = input?.parentElement;
  if (!row) return null;
  const existing = row.querySelector<HTMLElement>(
    "[data-company-candidate-review-shortcut]",
  );
  if (existing) return existing;
  const host = document.createElement("span");
  host.dataset.companyCandidateReviewShortcut = "true";
  host.style.display = "contents";
  row.appendChild(host);
  return host;
}

export function TrackingCompanyCandidateReview() {
  const mounted = useSyncExternalStore(
    emptyMountSubscribe,
    () => true,
    () => false,
  );
  const [snapshot, setSnapshot] = useState<CompanyCandidateSnapshot>(
    companyCandidateSnapshot,
  );
  const [manifest, setManifest] = useState(() =>
    normalizeCompanyCandidateDecisionManifest(rawDecisions),
  );
  const [selectedKey, setSelectedKey] = useState(
    companyCandidateSnapshot.candidates[0]?.decisionKey ?? "",
  );
  const [filter, setFilter] = useState<CompanyCandidateStatus>("pending");
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [connected, setConnected] = useState(false);
  const [decisionSha, setDecisionSha] = useState("");
  const [drafts, setDrafts] = useState<
    Record<string, { note: string; mergedSlug: string }>
  >({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(
    "登录后可在此审核、拒绝或合并候选；所有决定会写入版本化审核清单。",
  );
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [shortcutHost, setShortcutHost] = useState<HTMLElement | null>(null);

  const candidates = useMemo(
    () => applyCompanyCandidateDecisions(snapshot.candidates, manifest),
    [manifest, snapshot.candidates],
  );
  const counts = useMemo(() => countCompanyCandidateReviews(candidates), [candidates]);
  const filtered = useMemo(
    () => candidates.filter((candidate) => candidate.status === filter),
    [candidates, filter],
  );
  const selected = useMemo(
    () =>
      filtered.find((candidate) => candidate.decisionKey === selectedKey) ??
      filtered[0],
    [filtered, selectedKey],
  );
  const selectedDecision = selected
    ? decisionForCompanyCandidate(selected, manifest)
    : undefined;
  const selectedDraft = selected ? drafts[selected.decisionKey] : undefined;
  const note = selectedDraft?.note ?? selectedDecision?.note ?? selected?.note ?? "";
  const mergedSlug =
    selectedDraft?.mergedSlug ??
    selectedDecision?.mergedSlug ??
    selected?.mergedSlug ??
    "";

  const loadReviewData = useCallback(async (providedToken?: string) => {
    const cleanToken = (providedToken ?? currentToken()).trim();
    if (!cleanToken) {
      setConnected(false);
      setUsername("");
      setStatus("请先在页面上方完成管理员登录。");
      setStatusKind("error");
      return;
    }

    setBusy(true);
    setStatus("正在验证管理员并载入最新候选审核数据……");
    setStatusKind("neutral");
    try {
      const user = await githubJson<{ login: string }>(
        `${API_ROOT}/user`,
        cleanToken,
      );
      if (user.login.toLocaleLowerCase("en-US") !== TRACKING_OWNER.toLocaleLowerCase("en-US")) {
        throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}`);
      }
      const [candidateFile, decisionFile] = await Promise.all([
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${CANDIDATE_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISION_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
      ]);
      const nextSnapshot = normalizeCompanyCandidateSnapshot(
        JSON.parse(decodeBase64(candidateFile.content)),
      );
      const nextManifest = normalizeCompanyCandidateDecisionManifest(
        JSON.parse(decodeBase64(decisionFile.content)),
      );
      setToken(cleanToken);
      setUsername(user.login);
      setConnected(true);
      setSnapshot(nextSnapshot);
      setManifest(nextManifest);
      setDecisionSha(decisionFile.sha);
      setSelectedKey((current) => {
        if (nextSnapshot.candidates.some((candidate) => candidate.decisionKey === current)) {
          return current;
        }
        return (
          nextSnapshot.candidates.find((candidate) => candidate.status === "pending")
            ?.decisionKey ??
          nextSnapshot.candidates[0]?.decisionKey ??
          ""
        );
      });
      setStatus(
        `管理员 ${user.login} 已连接。审核决定将直接提交到 ${TRACKING_BRANCH}。`,
      );
      setStatusKind("success");
    } catch (error) {
      setConnected(false);
      setUsername("");
      setDecisionSha("");
      setStatus(`载入失败：${error instanceof Error ? error.message : String(error)}`);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const saved = currentToken();
    if (saved) {
      window.setTimeout(() => void loadReviewData(saved), 0);
    }

    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof Element)) return;
      const button = target.closest("button");
      const label = button?.textContent?.trim() ?? "";
      if (/登录|重新载入/.test(label)) {
        window.setTimeout(() => {
          const latest = currentToken();
          setToken(latest);
          if (latest) void loadReviewData(latest);
        }, 0);
      }
      if (label === "退出") {
        setToken("");
        setUsername("");
        setConnected(false);
        setDecisionSha("");
        setStatus("管理员已退出。审核数据仍可查看，但操作按钮已锁定。");
        setStatusKind("neutral");
      }
    };

    document.addEventListener("click", onClick, true);
    return () => document.removeEventListener("click", onClick, true);
  }, [loadReviewData, mounted]);

  useEffect(() => {
    if (!mounted) return;
    let frame = 0;
    const scan = () => {
      frame = 0;
      setShortcutHost((current) => current ?? ensureShortcutHost());
    };
    const schedule = () => {
      if (!frame) frame = window.requestAnimationFrame(scan);
    };
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    scan();
    return () => {
      if (frame) window.cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [mounted]);

  async function saveDecision(nextStatus: CompanyCandidateStatus) {
    if (!selected) return;
    const cleanToken = (token || currentToken()).trim();
    if (!cleanToken || !connected) {
      setStatus("请先在页面上方完成管理员登录，再执行审核操作。");
      setStatusKind("error");
      return;
    }
    const validation = validateCompanyCandidateDecision({
      status: nextStatus,
      note,
      mergedSlug,
    });
    if (!validation.valid) {
      setStatus(validation.message);
      setStatusKind("error");
      return;
    }

    setBusy(true);
    setStatus(`正在保存“${selected.name}”的审核决定……`);
    setStatusKind("neutral");
    try {
      const user = await githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken);
      if (user.login.toLocaleLowerCase("en-US") !== TRACKING_OWNER.toLocaleLowerCase("en-US")) {
        throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}`);
      }
      const [latestCandidatesFile, latestDecisionFile] = await Promise.all([
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${CANDIDATE_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
        githubJson<GithubFile>(
          `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISION_PATH}?ref=${TRACKING_BRANCH}`,
          cleanToken,
        ),
      ]);
      const latestSnapshot = normalizeCompanyCandidateSnapshot(
        JSON.parse(decodeBase64(latestCandidatesFile.content)),
      );
      const latestCandidate = latestSnapshot.candidates.find(
        (candidate) => candidate.decisionKey === selected.decisionKey,
      );
      if (!latestCandidate) {
        setSnapshot(latestSnapshot);
        throw new Error("该候选已不在最新审核池中，请重新载入后确认。");
      }
      if (
        companyCandidateEvidenceFingerprint(latestCandidate) !==
        companyCandidateEvidenceFingerprint(selected)
      ) {
        setSnapshot(latestSnapshot);
        throw new Error("候选证据已发生变化，已载入最新数据，请重新审核。");
      }

      const latestManifest = normalizeCompanyCandidateDecisionManifest(
        JSON.parse(decodeBase64(latestDecisionFile.content)),
      );
      const nextManifest = setCompanyCandidateDecision(
        latestManifest,
        selected.decisionKey,
        {
          status: nextStatus,
          note: nextStatus === "pending" ? "" : note,
          mergedSlug: nextStatus === "merged" ? mergedSlug : "",
          decidedAt: nextStatus === "pending" ? "" : new Date().toISOString(),
          reviewedBy: nextStatus === "pending" ? "" : user.login,
        },
      );
      const fileUrl = `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISION_PATH}`;
      const result = await githubJson<{
        content?: { sha?: string };
        commit?: { sha?: string };
      }>(fileUrl, cleanToken, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `review: ${nextStatus} company candidate ${selected.name}`,
          content: encodeBase64(`${JSON.stringify(orderedManifest(nextManifest), null, 2)}\n`),
          sha: latestDecisionFile.sha,
          branch: TRACKING_BRANCH,
        }),
      });
      const nextSha = result.content?.sha;
      if (!nextSha) throw new Error("GitHub 未返回新的审核清单 SHA。");

      setToken(cleanToken);
      setUsername(user.login);
      setConnected(true);
      setSnapshot(latestSnapshot);
      setManifest(nextManifest);
      setDecisionSha(nextSha);
      const commit = result.commit?.sha?.slice(0, 8) ?? "已创建";
      setStatus(
        nextStatus === "pending"
          ? `已恢复为待审核（${commit}）。`
          : `已保存为“${STATUS_LABELS[nextStatus]}”（${commit}）。候选快照和页面将由工作流更新。`,
      );
      setStatusKind("success");
    } catch (error) {
      setStatus(`保存失败：${error instanceof Error ? error.message : String(error)}`);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  }

  const shortcut = shortcutHost
    ? createPortal(
        <a className={styles.shortcut} href="#company-candidate-review">
          人工审核 <strong>{counts.pending}</strong>
        </a>,
        shortcutHost,
      )
    : null;

  return (
    <>
      {shortcut}
      <section
        className={styles.section}
        id="company-candidate-review"
        aria-labelledby="company-candidate-review-title"
      >
        <header className={styles.header}>
          <div>
            <p className="eyebrow">CANDIDATE COMPANY REVIEW</p>
            <h2 id="company-candidate-review-title">候选公司人工审核</h2>
            <p>
              查看候选证据并执行通过、拒绝或合并操作。决定写入
              <code> {DECISION_PATH}</code>，不会自动把候选加入正式公司档案。
            </p>
          </div>
          <div className={styles.summary} aria-label="候选审核统计">
            <span><small>待审核</small><strong>{counts.pending}</strong></span>
            <span><small>已通过</small><strong>{counts.accepted}</strong></span>
            <span><small>已拒绝</small><strong>{counts.rejected}</strong></span>
            <span><small>已合并</small><strong>{counts.merged}</strong></span>
          </div>
        </header>

        <div className={styles.toolbar}>
          <div className={styles.filters} role="tablist" aria-label="候选审核状态">
            {FILTERS.map((item) => (
              <button
                aria-selected={filter === item}
                data-active={filter === item}
                key={item}
                onClick={() => setFilter(item)}
                role="tab"
                type="button"
              >
                {STATUS_LABELS[item]} {counts[item]}
              </button>
            ))}
          </div>
          <button
            className={styles.reload}
            disabled={busy}
            onClick={() => void loadReviewData(token || currentToken())}
            type="button"
          >
            <RefreshCw size={15} aria-hidden="true" />
            重新载入审核池
          </button>
        </div>

        <p className={styles.status} data-kind={statusKind}>
          {status}
          {connected && decisionSha ? ` 审核清单 ${decisionSha.slice(0, 8)}。` : ""}
        </p>

        {candidates.length ? (
          <div className={styles.workspace}>
            <nav className={styles.candidateList} aria-label="候选公司列表">
              {filtered.length ? filtered.map((candidate) => (
                <button
                  data-active={candidate.decisionKey === selected?.decisionKey}
                  key={candidate.decisionKey}
                  onClick={() => setSelectedKey(candidate.decisionKey)}
                  type="button"
                >
                  <span className={styles.listTop}>
                    <b>{candidate.name}</b>
                    <em data-status={candidate.status}>{STATUS_LABELS[candidate.status]}</em>
                  </span>
                  <span>{candidate.region} · {candidate.sector}</span>
                  <span>评分 {candidate.score} · {candidate.articleCount} 条记录 · {candidate.sourceCount} 个来源</span>
                </button>
              )) : (
                <div className={styles.empty}>当前状态下没有候选。</div>
              )}
            </nav>

            {selected ? (
              <CandidateReviewDetail
                busy={busy}
                connected={connected}
                mergedSlug={mergedSlug}
                note={note}
                onMergedSlugChange={(value) =>
                  setDrafts((current) => ({
                    ...current,
                    [selected.decisionKey]: {
                      note,
                      mergedSlug: value,
                    },
                  }))
                }
                onNoteChange={(value) =>
                  setDrafts((current) => ({
                    ...current,
                    [selected.decisionKey]: {
                      note: value,
                      mergedSlug,
                    },
                  }))
                }
                onSave={saveDecision}
                selected={selected}
                username={username}
              />
            ) : (
              <div className={styles.empty}>当前没有可审核的候选公司。</div>
            )}
          </div>
        ) : (
          <div className={styles.empty}>当前候选审核池为空。</div>
        )}
      </section>
    </>
  );
}

function CandidateReviewDetail({
  selected,
  note,
  mergedSlug,
  connected,
  busy,
  username,
  onNoteChange,
  onMergedSlugChange,
  onSave,
}: {
  selected: ReviewedCompanyCandidate;
  note: string;
  mergedSlug: string;
  connected: boolean;
  busy: boolean;
  username: string;
  onNoteChange: (value: string) => void;
  onMergedSlugChange: (value: string) => void;
  onSave: (status: CompanyCandidateStatus) => Promise<void>;
}) {
  return (
    <article className={styles.detail}>
      <header className={styles.detailHeader}>
        <div>
          <p className="section-index">REVIEW EVIDENCE</p>
          <h3>{selected.name}</h3>
          <p>{selected.region} · {selected.sector} · 证据评分 {selected.score}</p>
        </div>
        <span className={styles.statusBadge} data-status={selected.status}>
          <ShieldCheck size={14} aria-hidden="true" />
          {STATUS_LABELS[selected.status]}
        </span>
      </header>

      <dl className={styles.facts}>
        <div><dt>审核键</dt><dd>{selected.decisionKey}</dd></div>
        <div><dt>结构化记录</dt><dd>{selected.articleCount}</dd></div>
        <div><dt>独立来源</dt><dd>{selected.sourceCount}</dd></div>
        <div><dt>最近证据</dt><dd>{displayTime(selected.lastSeenAt)}</dd></div>
      </dl>

      <section className={styles.evidenceBlock}>
        <h4>进入审核池的理由</h4>
        <ul>
          {selected.reasons.map((reason) => <li key={reason}>{reason}</li>)}
        </ul>
      </section>

      <section className={styles.evidenceBlock}>
        <h4>原始证据</h4>
        <div className={styles.sourceLinks}>
          {selected.sourceUrls.map((url, index) => (
            <a href={url} key={url} rel="noreferrer" target="_blank">
              来源 {index + 1}
              <span>{sourceHost(url)}</span>
              <ArrowUpRight size={13} aria-hidden="true" />
            </a>
          ))}
        </div>
      </section>

      <div className={styles.reviewForm}>
        <label>
          审核说明
          <textarea
            onChange={(event) => onNoteChange(event.target.value)}
            placeholder="说明为什么确认这是独立公司，或为什么应拒绝该候选。"
            value={note}
          />
        </label>
        <label>
          已有公司档案 slug（仅“合并”使用）
          <input
            onChange={(event) => onMergedSlugChange(event.target.value)}
            placeholder="例如 shopify"
            value={mergedSlug}
          />
        </label>
        <p className={styles.auditNote}>
          {selected.decidedAt
            ? `最近决定：${displayTime(selected.decidedAt)} · ${selected.reviewedBy || username || "管理员"}`
            : `当前操作人：${username || "请先登录"}`}
        </p>
        <div className={styles.actions}>
          <button
            className={styles.accept}
            disabled={!connected || busy}
            onClick={() => void onSave("accepted")}
            type="button"
          >
            <Check size={15} aria-hidden="true" />审核通过
          </button>
          <button
            className={styles.reject}
            disabled={!connected || busy}
            onClick={() => void onSave("rejected")}
            type="button"
          >
            <X size={15} aria-hidden="true" />拒绝候选
          </button>
          <button
            className={styles.merge}
            disabled={!connected || busy}
            onClick={() => void onSave("merged")}
            type="button"
          >
            <GitMerge size={15} aria-hidden="true" />合并到已有档案
          </button>
          {selected.status !== "pending" && (
            <button
              className={styles.reset}
              disabled={!connected || busy}
              onClick={() => void onSave("pending")}
              type="button"
            >
              <RotateCcw size={15} aria-hidden="true" />恢复待审核
            </button>
          )}
        </div>
        <p className={styles.boundary}>
          “审核通过”只确认候选资格，不会自动创建正式公司页面；完成公司档案后，再使用“合并到已有档案”。
        </p>
      </div>
    </article>
  );
}
