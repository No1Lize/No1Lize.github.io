"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ArrowUpRight, Building2, RefreshCw, Send, ShieldAlert } from "lucide-react";
import rawDecisions from "@/config/company_candidate_decisions.json";
import {
  companyCandidateSnapshot,
  normalizeCompanyCandidateSnapshot,
  type CompanyCandidateSnapshot,
} from "@/lib/company-candidate-data";
import {
  applyCompanyCandidateDecisions,
  companyCandidateEvidenceFingerprint,
  normalizeCompanyCandidateDecisionManifest,
  type CompanyCandidateDecisionManifest,
  type ReviewedCompanyCandidate,
} from "@/lib/company-candidate-review";
import {
  emptyCompanyOnboardingProfile,
  normalizeCompanyOnboardingProfile,
  requestCompanyCandidateOnboarding,
  validateCompanyOnboardingProfile,
  type CompanyOnboardingProfile,
} from "@/lib/company-candidate-onboarding";
import {
  TRACKING_BRANCH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import styles from "./tracking-company-onboarding.module.css";

const API_ROOT = "https://api.github.com";
const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
const CANDIDATE_PATH = "public/data/company_candidates.json";
const DECISION_PATH = "config/company_candidate_decisions.json";

type GithubFile = { sha: string; content: string };
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
  return window.sessionStorage.getItem(TOKEN_SESSION_KEY)?.trim() ?? "";
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

function onboardingLabel(candidate: ReviewedCompanyCandidate) {
  const status = candidate.onboarding?.status;
  if (candidate.status === "published" || status === "published") return "已发布";
  if (status === "requested") return "等待自动建档";
  if (status === "failed") return "建档失败";
  return "待补建档资料";
}

function profileForCandidate(candidate: ReviewedCompanyCandidate) {
  const existing = candidate.onboarding?.profile;
  if (existing?.slug || existing?.homepage || existing?.summary) {
    return normalizeCompanyOnboardingProfile(existing);
  }
  return emptyCompanyOnboardingProfile(candidate);
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  textarea = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  textarea?: boolean;
}) {
  return (
    <label>
      <span>{label}</span>
      {textarea ? (
        <textarea
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          value={value}
        />
      ) : (
        <input
          onChange={(event) => onChange(event.target.value)}
          placeholder={placeholder}
          value={value}
        />
      )}
    </label>
  );
}

export function TrackingCompanyOnboarding() {
  const [snapshot, setSnapshot] = useState<CompanyCandidateSnapshot>(companyCandidateSnapshot);
  const [manifest, setManifest] = useState(() =>
    normalizeCompanyCandidateDecisionManifest(rawDecisions),
  );
  const [token, setToken] = useState("");
  const [connected, setConnected] = useState(false);
  const [selectedKey, setSelectedKey] = useState("");
  const [profiles, setProfiles] = useState<Record<string, CompanyOnboardingProfile>>({});
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState(
    "审核通过后，在此补齐规范公司实体和官方主页；提交后由工作流自动建档、抓取、校验并发布。",
  );
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");

  const reviewed = useMemo(
    () => applyCompanyCandidateDecisions(snapshot.candidates, manifest),
    [manifest, snapshot.candidates],
  );
  const eligible = useMemo(
    () =>
      reviewed.filter(
        (candidate) => candidate.status === "accepted" || candidate.status === "published",
      ),
    [reviewed],
  );
  const selected = useMemo(
    () => eligible.find((candidate) => candidate.decisionKey === selectedKey) ?? eligible[0],
    [eligible, selectedKey],
  );
  const profile = selected
    ? profiles[selected.decisionKey] ?? profileForCandidate(selected)
    : undefined;
  const counts = useMemo(
    () => ({
      awaiting: eligible.filter(
        (candidate) =>
          candidate.status === "accepted" &&
          !["requested", "failed"].includes(candidate.onboarding?.status ?? ""),
      ).length,
      requested: eligible.filter((candidate) => candidate.onboarding?.status === "requested").length,
      failed: eligible.filter((candidate) => candidate.onboarding?.status === "failed").length,
      published: eligible.filter((candidate) => candidate.status === "published").length,
    }),
    [eligible],
  );

  const load = useCallback(async (providedToken?: string) => {
    const cleanToken = (providedToken ?? currentToken()).trim();
    if (!cleanToken) {
      setConnected(false);
      setStatus("请先在页面上方完成管理员登录。");
      setStatusKind("error");
      return;
    }
    setBusy(true);
    setStatus("正在载入最新候选、审核决定和建档状态……");
    setStatusKind("neutral");
    try {
      const user = await githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken);
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
      const nextReviewed = applyCompanyCandidateDecisions(
        nextSnapshot.candidates,
        nextManifest,
      ).filter((candidate) =>
        candidate.status === "accepted" || candidate.status === "published",
      );
      setToken(cleanToken);
      setConnected(true);
      setSnapshot(nextSnapshot);
      setManifest(nextManifest);
      setProfiles(
        Object.fromEntries(
          nextReviewed.map((candidate) => [
            candidate.decisionKey,
            profileForCandidate(candidate),
          ]),
        ),
      );
      setSelectedKey((current) =>
        nextReviewed.some((candidate) => candidate.decisionKey === current)
          ? current
          : nextReviewed[0]?.decisionKey ?? "",
      );
      setStatus(`管理员 ${user.login} 已连接。提交建档请求后将由 GitHub 工作流自动处理。`);
      setStatusKind("success");
    } catch (error) {
      setConnected(false);
      setStatus(`载入失败：${error instanceof Error ? error.message : String(error)}`);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    const saved = currentToken();
    if (!saved) return;
    const timer = window.setTimeout(() => {
      void load(saved);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  function updateProfile<K extends keyof CompanyOnboardingProfile>(
    key: K,
    value: CompanyOnboardingProfile[K],
  ) {
    if (!selected || !profile) return;
    setProfiles((current) => ({
      ...current,
      [selected.decisionKey]: { ...profile, [key]: value },
    }));
  }

  async function submit() {
    if (!selected || !profile) return;
    const validation = validateCompanyOnboardingProfile(profile, selected);
    if (!validation.valid) {
      setStatus(validation.message);
      setStatusKind("error");
      return;
    }
    const cleanToken = (token || currentToken()).trim();
    if (!cleanToken || !connected) {
      setStatus("请先完成管理员登录。");
      setStatusKind("error");
      return;
    }

    setBusy(true);
    setStatus(`正在提交“${profile.name}”的自动建档请求……`);
    setStatusKind("neutral");
    try {
      const user = await githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken);
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
      const latestSnapshot = normalizeCompanyCandidateSnapshot(
        JSON.parse(decodeBase64(candidateFile.content)),
      );
      const latestCandidate = latestSnapshot.candidates.find(
        (candidate) => candidate.decisionKey === selected.decisionKey,
      );
      if (!latestCandidate) throw new Error("该候选已不在最新审核池中。");
      if (
        companyCandidateEvidenceFingerprint(latestCandidate) !==
        companyCandidateEvidenceFingerprint(selected)
      ) {
        setSnapshot(latestSnapshot);
        throw new Error("候选证据已变化，请重新载入并复核后再提交。");
      }
      const latestManifest = normalizeCompanyCandidateDecisionManifest(
        JSON.parse(decodeBase64(decisionFile.content)),
      );
      const nextManifest = requestCompanyCandidateOnboarding({
        manifest: latestManifest,
        candidate: latestCandidate,
        profile,
        requestedBy: user.login,
        requestedAt: new Date().toISOString(),
      });
      const result = await githubJson<{
        content?: { sha?: string };
        commit?: { sha?: string };
      }>(`${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${DECISION_PATH}`, cleanToken, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `onboard: request company profile ${profile.slug}`,
          content: encodeBase64(`${JSON.stringify(orderedManifest(nextManifest), null, 2)}\n`),
          sha: decisionFile.sha,
          branch: TRACKING_BRANCH,
        }),
      });
      setToken(cleanToken);
      setManifest(nextManifest);
      const commit = result.commit?.sha?.slice(0, 8) ?? "已创建";
      setStatus(
        `自动建档请求已提交（${commit}）。工作流将更新公司注册表、官方来源、档案数据和正式页面。`,
      );
      setStatusKind("success");
    } catch (error) {
      setStatus(`提交失败：${error instanceof Error ? error.message : String(error)}`);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className={styles.section} id="company-candidate-onboarding">
      <header className={styles.header}>
        <div>
          <p className="eyebrow">COMPANY PROFILE ONBOARDING</p>
          <h2>审核通过后的自动建档</h2>
          <p>
            “审核通过”只确认公司实体。补齐规范名称、slug 和官方来源后，系统会自动写入公司注册表、首次抓取档案并创建
            <code> /companies/&lt;slug&gt;</code> 页面。
          </p>
        </div>
        <dl className={styles.summary}>
          <div><dt>待补资料</dt><dd>{counts.awaiting}</dd></div>
          <div><dt>处理中</dt><dd>{counts.requested}</dd></div>
          <div><dt>失败</dt><dd>{counts.failed}</dd></div>
          <div><dt>已发布</dt><dd>{counts.published}</dd></div>
        </dl>
      </header>

      <div className={styles.toolbar}>
        <p className={styles.status} data-kind={statusKind}>{status}</p>
        <button disabled={busy} onClick={() => void load(token || currentToken())} type="button">
          <RefreshCw size={15} aria-hidden="true" />重新载入建档状态
        </button>
      </div>

      {eligible.length && selected && profile ? (
        <div className={styles.workspace}>
          <nav className={styles.list} aria-label="已通过候选">
            {eligible.map((candidate) => (
              <button
                data-active={candidate.decisionKey === selected.decisionKey}
                key={candidate.decisionKey}
                onClick={() => setSelectedKey(candidate.decisionKey)}
                type="button"
              >
                <strong>{candidate.name}</strong>
                <span>{onboardingLabel(candidate)}</span>
                <small>{candidate.region} · {candidate.sector} · 评分 {candidate.score}</small>
              </button>
            ))}
          </nav>

          <article className={styles.form}>
            <header>
              <div>
                <p className="section-index">CANONICAL ENTITY</p>
                <h3>{selected.name}</h3>
              </div>
              <span data-state={selected.onboarding?.status ?? "awaiting_profile"}>
                <Building2 size={15} aria-hidden="true" />{onboardingLabel(selected)}
              </span>
            </header>

            {selected.onboarding?.status === "failed" && (
              <p className={styles.error}><ShieldAlert size={15} />{selected.onboarding.error}</p>
            )}
            {selected.status === "published" ? (
              <div className={styles.published}>
                <strong>正式公司档案已发布</strong>
                <a href={`/companies/${selected.mergedSlug}`}>
                  查看 {selected.mergedSlug}<ArrowUpRight size={14} />
                </a>
              </div>
            ) : (
              <>
                <div className={styles.grid}>
                  <Field label="页面 slug" value={profile.slug} onChange={(value) => updateProfile("slug", value)} placeholder="shopify" />
                  <Field label="规范公司名称" value={profile.name} onChange={(value) => updateProfile("name", value)} />
                  <Field label="英文名称" value={profile.englishName} onChange={(value) => updateProfile("englishName", value)} />
                  <Field label="地区" value={profile.region} onChange={(value) => updateProfile("region", value)} placeholder="中国、美国、加拿大" />
                  <Field label="赛道" value={profile.sector} onChange={(value) => updateProfile("sector", value)} />
                  <Field label="阶段" value={profile.stage} onChange={(value) => updateProfile("stage", value)} placeholder="成长期、已上市" />
                  <label>
                    <span>运营状态</span>
                    <select value={profile.status} onChange={(event) => updateProfile("status", event.target.value as CompanyOnboardingProfile["status"])}>
                      <option value="运营中">运营中</option>
                      <option value="已上市">已上市</option>
                    </select>
                  </label>
                  <Field label="成立时间" value={profile.founded} onChange={(value) => updateProfile("founded", value)} />
                  <Field label="总部" value={profile.headquarters} onChange={(value) => updateProfile("headquarters", value)} />
                  <Field label="官方主页" value={profile.homepage} onChange={(value) => updateProfile("homepage", value)} placeholder="https://..." />
                  <Field label="公司简介" value={profile.summary} onChange={(value) => updateProfile("summary", value)} textarea />
                  <Field label="核心产品" value={profile.product} onChange={(value) => updateProfile("product", value)} textarea />
                  <Field
                    label="别名（逗号分隔）"
                    value={profile.aliases.join(", ")}
                    onChange={(value) => updateProfile("aliases", value.split(/[,，]/u).map((item) => item.trim()).filter(Boolean))}
                  />
                  <Field
                    label="新闻 / 公告入口（每行一个）"
                    value={profile.newsUrls.join("\n")}
                    onChange={(value) => updateProfile("newsUrls", value.split(/\n/u).map((item) => item.trim()).filter(Boolean))}
                    textarea
                  />
                </div>
                <p className={styles.note}>
                  人物姓名、媒体文章来源或产品名不能直接建档。此类候选应改填规范公司实体，或回到上方使用“合并到已有档案”。
                </p>
                <button className={styles.submit} disabled={!connected || busy} onClick={() => void submit()} type="button">
                  <Send size={15} aria-hidden="true" />提交自动建档
                </button>
              </>
            )}
          </article>
        </div>
      ) : (
        <div className={styles.empty}>当前没有已审核通过、需要建档的候选公司。</div>
      )}
    </section>
  );
}
