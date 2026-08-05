"use client";

import {
  ArrowLeft,
  Building2,
  Copy,
  Cpu,
  Download,
  ExternalLink,
  Globe2,
  LoaderCircle,
  Plus,
  ShieldCheck,
  UserRound,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  externalTrackingCaptureBookmarklet,
  parseExternalTrackingCaptureParams,
  recommendExternalTrackingCaptureTracks,
} from "@/lib/external-tracking-capture";
import {
  TRACKING_ADMIN_TOKEN_SESSION_KEY,
  TRACKING_CAPTURE_CHANGED_EVENT,
  applyTrackingCapture,
  stableTrackingCaptureHash,
  type TrackingCaptureEntityDraft,
  type TrackingCaptureEntityType,
  type TrackingCaptureSource,
} from "@/lib/tracking-capture";
import {
  TrackingCaptureConflictError,
  commitTrackingCaptureRepositoryState,
  fetchTrackingCaptureRepositoryState,
} from "@/lib/tracking-capture-github";
import {
  cloneTrackingConfig,
  userTrackingConfig,
  type UserTrackingConfig,
} from "@/lib/user-tracking";
import styles from "./external-tracking-capture-page.module.css";

type EntityRow = TrackingCaptureEntityDraft & { id: string };
type StatusKind = "neutral" | "success" | "error";

const RESEARCH_REASON_OPTIONS = [
  "融资机会",
  "技术突破",
  "商业模式创新",
  "市场竞争",
  "IPO可能",
  "监管变化",
  "个人研究兴趣",
] as const;

const EMPTY_SOURCE: TrackingCaptureSource = {
  articleId: "",
  title: "",
  url: "",
  summary: "",
  sourceName: "外部网页",
  channel: "external",
  channelLabel: "外部网页",
  eventType: "外部文章采集",
};

function makeEntityRow(
  entityType: TrackingCaptureEntityType,
  name = "",
): EntityRow {
  return {
    id: `external-entity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    entityType,
    name,
  };
}

function initialToken() {
  if (typeof window === "undefined") return "";
  return window.sessionStorage.getItem(TRACKING_ADMIN_TOKEN_SESSION_KEY) ?? "";
}

function validHttpUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

export function ExternalTrackingCapturePage() {
  const [source, setSource] = useState<TrackingCaptureSource>(EMPTY_SOURCE);
  const [selectedText, setSelectedText] = useState("");
  const [entities, setEntities] = useState<EntityRow[]>([
    makeEntityRow("company"),
  ]);
  const [config, setConfig] = useState<UserTrackingConfig>(() =>
    cloneTrackingConfig(userTrackingConfig),
  );
  const [selectedTrackSlugs, setSelectedTrackSlugs] = useState<string[]>([]);
  const [newTrackName, setNewTrackName] = useState("");
  const [reasons, setReasons] = useState<string[]>([]);
  const [note, setNote] = useState("");
  const [token, setToken] = useState(initialToken);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [status, setStatus] = useState(
    "可从浏览器扩展、书签脚本或手动粘贴进入此页面。",
  );
  const [copyStatus, setCopyStatus] = useState("");

  useEffect(() => {
    const prefill = parseExternalTrackingCaptureParams(
      new URLSearchParams(window.location.search),
    );
    setSource(prefill.source);
    setSelectedText(prefill.selectedText);
    setEntities(
      prefill.entities.length
        ? prefill.entities.map((entity) =>
            makeEntityRow(entity.entityType, entity.name),
          )
        : [makeEntityRow("company")],
    );
    setSelectedTrackSlugs(
      recommendExternalTrackingCaptureTracks(prefill, userTrackingConfig),
    );
    setReady(true);
  }, []);

  const usableEntities = useMemo(
    () => entities.filter((entity) => entity.name.trim()),
    [entities],
  );

  function updateSource(patch: Partial<TrackingCaptureSource>) {
    setSource((current) => ({ ...current, ...patch }));
  }

  function addEntity(entityType: TrackingCaptureEntityType) {
    setEntities((current) => [...current, makeEntityRow(entityType)]);
  }

  function updateEntity(id: string, patch: Partial<EntityRow>) {
    setEntities((current) =>
      current.map((entity) =>
        entity.id === id ? { ...entity, ...patch } : entity,
      ),
    );
  }

  function removeEntity(id: string) {
    setEntities((current) => {
      const next = current.filter((entity) => entity.id !== id);
      return next.length ? next : [makeEntityRow("company")];
    });
  }

  function toggleTrack(slug: string) {
    setSelectedTrackSlugs((current) =>
      current.includes(slug)
        ? current.filter((candidate) => candidate !== slug)
        : [...current, slug],
    );
  }

  function toggleReason(reason: string) {
    setReasons((current) =>
      current.includes(reason)
        ? current.filter((candidate) => candidate !== reason)
        : [...current, reason],
    );
  }

  async function copyBookmarklet() {
    try {
      await copyText(externalTrackingCaptureBookmarklet());
      setCopyStatus("书签脚本已复制。请新建浏览器书签，并把脚本粘贴到网址栏。");
    } catch (error) {
      setCopyStatus(
        `复制失败：${error instanceof Error ? error.message : String(error)}`,
      );
    }
  }

  async function submit() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setStatusKind("error");
      setStatus("请填写仓库 Fine-grained Token；权限需要 Contents: Read and write。");
      return;
    }
    if (!source.title.trim() || !validHttpUrl(source.url)) {
      setStatusKind("error");
      setStatus("请填写完整的外部文章标题和公开 HTTP(S) URL。");
      return;
    }
    if (!usableEntities.length) {
      setStatusKind("error");
      setStatus("请至少填写一个公司、人物或技术／主题。");
      return;
    }

    window.sessionStorage.setItem(TRACKING_ADMIN_TOKEN_SESSION_KEY, cleanToken);
    setBusy(true);
    setStatusKind("neutral");
    setStatus("正在核对管理员身份、远端配置和文章采集箱……");

    try {
      let lastConflict: Error | null = null;
      for (let attempt = 0; attempt < 2; attempt += 1) {
        const remote = await fetchTrackingCaptureRepositoryState(cleanToken);
        setConfig(remote.config);
        const capturedAt = new Date().toISOString();
        const preparedSource: TrackingCaptureSource = {
          ...source,
          articleId: `external-${stableTrackingCaptureHash(
            `${source.title}|${source.url}`,
          )}`,
          title: source.title.trim(),
          url: source.url.trim(),
          sourceName: source.sourceName.trim() || "外部网页",
          channel: "external",
          channelLabel: "外部网页",
          eventType: source.eventType.trim() || "外部文章采集",
        };
        const result = applyTrackingCapture({
          config: remote.config,
          inbox: remote.inbox,
          entities: usableEntities.map(({ entityType, name }) => ({
            entityType,
            name,
          })),
          selectedTrackSlugs,
          newTrackName,
          reasons,
          note,
          source: preparedSource,
          capturedAt,
          capturedBy: remote.username,
        });
        try {
          const commitSha = await commitTrackingCaptureRepositoryState(
            cleanToken,
            remote,
            { config: result.config, inbox: result.inbox },
          );
          setConfig(result.config);
          setSelectedTrackSlugs(result.trackSlugs);
          setStatusKind("success");
          setStatus(
            `已提交 ${result.records.length} 个追踪对象（${commitSha.slice(0, 8)}）。新增 ${result.addedCount} 项，重复 ${result.duplicateCount} 项；公司对象将进入候选审核流程。`,
          );
          window.dispatchEvent(
            new CustomEvent(TRACKING_CAPTURE_CHANGED_EVENT, {
              detail: result.records,
            }),
          );
          return;
        } catch (error) {
          if (error instanceof TrackingCaptureConflictError) {
            lastConflict = error;
            setStatus("远端刚刚发生变化，正在基于最新 main 自动重试……");
            continue;
          }
          throw error;
        }
      }
      throw lastConflict ?? new Error("远端配置持续变化，请稍后重试。");
    } catch (error) {
      setStatusKind("error");
      setStatus(`提交失败：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return (
      <main className="page-shell subpage">
        <div className={styles.loading}>
          <LoaderCircle size={22} className={styles.spinning} />
          正在读取外部文章信息……
        </div>
      </main>
    );
  }

  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div>
          <Link href="/tracking" className={styles.back}>
            <ArrowLeft size={15} />网站追踪管理
          </Link>
          <p className="eyebrow">EXTERNAL ARTICLE CAPTURE</p>
          <h1>外部文章采集</h1>
          <p>
            在新浪财经、监管网站或其他公开网页中选中文字后，将公司、人物和技术主题连同原始文章证据送入 VCIQ。扩展和书签脚本不保存 GitHub Token。
          </p>
        </div>
        <div className={styles.heroActions}>
          <Link href="/tracking/entities">追踪对象研究库</Link>
          <Link href="/tracking#tracking-capture-inbox">文章采集箱</Link>
        </div>
      </header>

      <section className={styles.installGrid} aria-labelledby="capture-tools-title">
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">CAPTURE TOOLS</p>
            <h2 id="capture-tools-title">从外部网页一键进入</h2>
          </div>
          <p>扩展适合长期使用；书签脚本无需安装扩展。</p>
        </div>
        <div className={styles.installCards}>
          <article>
            <Globe2 size={22} />
            <h3>Chrome / Edge 扩展</h3>
            <p>选中文字后右键，可直接标记为公司、人物或技术主题；也可采集整篇网页。</p>
            <a
              href="/downloads/vciq-tracking-capture-extension.zip"
              download
              className={styles.primaryLink}
            >
              <Download size={15} />下载扩展包
            </a>
            <small>解压后在浏览器扩展管理页开启开发者模式，再选择“加载已解压的扩展程序”。</small>
          </article>
          <article>
            <Copy size={22} />
            <h3>划词采集书签</h3>
            <p>把脚本保存为浏览器书签。阅读任意网页时选中文字，再点击该书签。</p>
            <button type="button" onClick={() => void copyBookmarklet()}>
              <Copy size={15} />复制书签脚本
            </button>
            <small>{copyStatus || "脚本只读取当前页面标题、URL 和你主动选中的文字。"}</small>
          </article>
        </div>
      </section>

      <div className={styles.workspace}>
        <section className={styles.mainColumn}>
          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">01 / SOURCE</p>
                <h2>原始文章与选中文本</h2>
              </div>
              {validHttpUrl(source.url) ? (
                <a href={source.url} target="_blank" rel="noreferrer">
                  查看原文 <ExternalLink size={13} />
                </a>
              ) : null}
            </div>
            {selectedText ? (
              <blockquote className={styles.selection}>{selectedText}</blockquote>
            ) : null}
            <div className={styles.sourceFields}>
              <label className={styles.wide}>
                <span>文章 URL</span>
                <input
                  type="url"
                  value={source.url}
                  disabled={busy}
                  placeholder="https://..."
                  onChange={(event) => updateSource({ url: event.target.value })}
                />
              </label>
              <label className={styles.wide}>
                <span>文章标题</span>
                <input
                  value={source.title}
                  disabled={busy}
                  maxLength={300}
                  onChange={(event) => updateSource({ title: event.target.value })}
                />
              </label>
              <label>
                <span>来源</span>
                <input
                  value={source.sourceName}
                  disabled={busy}
                  maxLength={160}
                  onChange={(event) =>
                    updateSource({ sourceName: event.target.value })
                  }
                />
              </label>
              <label>
                <span>事件类型</span>
                <input
                  value={source.eventType}
                  disabled={busy}
                  maxLength={80}
                  onChange={(event) =>
                    updateSource({ eventType: event.target.value })
                  }
                />
              </label>
              <label className={styles.wide}>
                <span>选中文本／上下文</span>
                <textarea
                  value={source.summary}
                  disabled={busy}
                  maxLength={1200}
                  placeholder="保留选中文字及必要上下文，作为为什么开始追踪的来源证据。"
                  onChange={(event) =>
                    updateSource({ summary: event.target.value })
                  }
                />
              </label>
            </div>
          </section>

          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">02 / ENTITIES</p>
                <h2>公司、人物和技术／主题</h2>
              </div>
              <span>{usableEntities.length} 项</span>
            </div>
            <div className={styles.entityList}>
              {entities.map((entity) => (
                <div className={styles.entityRow} key={entity.id}>
                  <select
                    value={entity.entityType}
                    disabled={busy}
                    aria-label="追踪对象类型"
                    onChange={(event) =>
                      updateEntity(entity.id, {
                        entityType: event.target.value as TrackingCaptureEntityType,
                      })
                    }
                  >
                    <option value="company">公司</option>
                    <option value="person">人物</option>
                    <option value="topic">技术／主题</option>
                  </select>
                  <input
                    value={entity.name}
                    disabled={busy}
                    onChange={(event) =>
                      updateEntity(entity.id, { name: event.target.value })
                    }
                    placeholder={
                      entity.entityType === "company"
                        ? "例如：Polymarket、Kalshi"
                        : entity.entityType === "person"
                          ? "例如：Shayne Coplan"
                          : "例如：预测市场、prediction market"
                    }
                  />
                  <button
                    type="button"
                    disabled={busy}
                    aria-label="移除追踪对象"
                    onClick={() => removeEntity(entity.id)}
                  >
                    <X size={15} />
                  </button>
                </div>
              ))}
            </div>
            <div className={styles.quickAdd}>
              <button type="button" disabled={busy} onClick={() => addEntity("company")}>
                <Building2 size={14} /> + 公司
              </button>
              <button type="button" disabled={busy} onClick={() => addEntity("person")}>
                <UserRound size={14} /> + 人物
              </button>
              <button type="button" disabled={busy} onClick={() => addEntity("topic")}>
                <Cpu size={14} /> + 技术／主题
              </button>
            </div>
          </section>

          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">03 / TRACKS</p>
                <h2>选择目标赛道</h2>
              </div>
              <span>{selectedTrackSlugs.length} 个</span>
            </div>
            <div className={styles.trackGrid}>
              {config.tracks
                .filter((track) => track.enabled)
                .map((track) => (
                  <label
                    key={track.slug}
                    data-selected={selectedTrackSlugs.includes(track.slug)}
                  >
                    <input
                      type="checkbox"
                      disabled={busy}
                      checked={selectedTrackSlugs.includes(track.slug)}
                      onChange={() => toggleTrack(track.slug)}
                    />
                    <span>{track.name}</span>
                  </label>
                ))}
            </div>
            <label className={styles.newTrack}>
              <span>或新建赛道</span>
              <input
                value={newTrackName}
                disabled={busy}
                maxLength={60}
                placeholder="例如：预测市场"
                onChange={(event) => setNewTrackName(event.target.value)}
              />
            </label>
          </section>

          <section className={styles.panel}>
            <div className={styles.sectionHeading}>
              <div>
                <p className="section-index">04 / RESEARCH INTENT</p>
                <h2>为什么关注</h2>
              </div>
              <span>{reasons.length} 个原因</span>
            </div>
            <div className={styles.reasonGrid}>
              {RESEARCH_REASON_OPTIONS.map((reason) => (
                <label key={reason} data-selected={reasons.includes(reason)}>
                  <input
                    type="checkbox"
                    disabled={busy}
                    checked={reasons.includes(reason)}
                    onChange={() => toggleReason(reason)}
                  />
                  <span>{reason}</span>
                </label>
              ))}
            </div>
            <label className={styles.note}>
              <span>研究备注</span>
              <textarea
                value={note}
                disabled={busy}
                maxLength={800}
                placeholder="例如：预测市场可能成为金融信息基础设施，重点观察监管、融资和与 Kalshi 的竞争。"
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
          </section>
        </section>

        <aside className={styles.sidebar}>
          <section>
            <p className="section-index">PUBLISH</p>
            <h2>提交到追踪系统</h2>
            <p>
              公司会立即进入目标赛道和候选审核池；人物进入人物追踪；技术主题进入关键词。正式公司建档仍保留人工审核质量门。
            </p>
            <label className={styles.token}>
              <span>GitHub Token</span>
              <input
                type="password"
                autoComplete="off"
                value={token}
                disabled={busy}
                placeholder="仅保存在当前标签页"
                onChange={(event) => setToken(event.target.value)}
              />
            </label>
            <button
              type="button"
              className={styles.submit}
              disabled={busy}
              onClick={() => void submit()}
            >
              {busy ? <LoaderCircle size={15} className={styles.spinning} /> : <Plus size={15} />}
              {busy ? "正在提交" : `添加并开始追踪 ${usableEntities.length} 项`}
            </button>
            <p className={styles.status} data-kind={statusKind} aria-live="polite">
              {status}
            </p>
            <p className={styles.security}>
              <ShieldCheck size={14} />
              扩展和书签脚本只传递页面标题、URL 与选中文字；Token 只在 VCIQ 页面当前标签页中使用。
            </p>
          </section>
        </aside>
      </div>
    </main>
  );
}
