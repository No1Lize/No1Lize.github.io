"use client";

import { useEffect, useMemo, useState } from "react";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
  cloneTrackingConfig,
  normalizeTrackingConfig,
  slugifyTrack,
  type TrackingRegion,
  type TrackingSource,
  type TrackingSourceType,
  type UserTrackingConfig,
} from "@/lib/user-tracking";
import styles from "./user-tracking-panel.module.css";

const API_ROOT = "https://api.github.com";
const LIST_FIELDS = ["keywords", "people", "sampleCompanies"] as const;
type ListField = (typeof LIST_FIELDS)[number];

type StatusKind = "neutral" | "success" | "error";

type SourceDraft = {
  name: string;
  url: string;
  sourceType: TrackingSourceType;
  region: TrackingRegion;
  sector: string;
  company: string;
  ticker: string;
  keywords: string;
};

const EMPTY_SOURCE: SourceDraft = {
  name: "",
  url: "",
  sourceType: "listing-search",
  region: "全球",
  sector: "AI / AGI",
  company: "",
  ticker: "",
  keywords: "",
};

const LABELS: Record<ListField, { title: string; placeholder: string; help: string }> = {
  keywords: {
    title: "追踪关键词",
    placeholder: "例如：VLA、固态电池",
    help: "会加入新闻、公开搜索和论文来源的筛选词。",
  },
  people: {
    title: "关键人物",
    placeholder: "例如：姚顺雨 @ShunyuYao12",
    help: "写入 @handle 时会额外生成 X 公开时间线来源。",
  },
  sampleCompanies: {
    title: "样本公司",
    placeholder: "例如：OpenAI、宇树科技",
    help: "会进入该赛道的公司与事件搜索词。",
  },
};

function encodeBase64(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...Array.from(bytes.subarray(index, index + 8192)));
  }
  return btoa(binary);
}

function decodeBase64(value: string): string {
  const binary = atob(value.replace(/\n/g, ""));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

async function githubJson<T>(url: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (!response.ok) {
    const message = typeof payload.message === "string" ? payload.message : text;
    throw new Error(`${response.status} ${message || "GitHub API 请求失败"}`);
  }
  return payload as T;
}

export function UserTrackingPanel({ initial }: { initial: UserTrackingConfig }) {
  const [config, setConfig] = useState(() => cloneTrackingConfig(initial));
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [remoteSha, setRemoteSha] = useState("");
  const [status, setStatus] = useState("尚未连接 GitHub。所有本地修改在同步前不会写入仓库。");
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const [newTrackName, setNewTrackName] = useState("");
  const [listInputs, setListInputs] = useState<Record<ListField, string>>({
    keywords: "",
    people: "",
    sampleCompanies: "",
  });
  const [sourceDraft, setSourceDraft] = useState<SourceDraft>(EMPTY_SOURCE);

  const track = config.tracks[active];
  const connected = Boolean(username && remoteSha);
  const enabledTracks = useMemo(
    () => config.tracks.filter((item) => item.enabled),
    [config.tracks],
  );

  useEffect(() => {
    if (active >= config.tracks.length) {
      setActive(Math.max(0, config.tracks.length - 1));
    }
  }, [active, config.tracks.length]);

  function update(next: UserTrackingConfig) {
    setConfig(normalizeTrackingConfig(next));
    setStatusKind("neutral");
    setStatus("存在尚未同步的本地修改。");
  }

  function setMessage(message: string, kind: StatusKind = "neutral") {
    setStatus(message);
    setStatusKind(kind);
  }

  async function loadFromGithub() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setMessage("请先输入 Fine-grained Token。", "error");
      return;
    }
    setBusy(true);
    try {
      setMessage("正在验证 GitHub 账号并读取远端配置……");
      const user = await githubJson<{ login: string }>(`${API_ROOT}/user`, cleanToken);
      if (user.login.toLowerCase() !== TRACKING_OWNER.toLowerCase()) {
        throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}`);
      }
      const file = await githubJson<{ sha: string; content: string }>(
        `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}?ref=${TRACKING_BRANCH}`,
        cleanToken,
      );
      const remoteConfig = normalizeTrackingConfig(JSON.parse(decodeBase64(file.content)));
      setConfig(remoteConfig);
      setRemoteSha(file.sha);
      setUsername(user.login);
      setActive(0);
      setMessage(`已连接 ${user.login}，当前配置已从 main 分支载入。`, "success");
    } catch (error) {
      setUsername("");
      setRemoteSha("");
      setMessage(`连接失败：${error instanceof Error ? error.message : String(error)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  async function syncGithub() {
    if (!connected || !token.trim()) {
      setMessage("请先连接 GitHub 并载入远端配置。", "error");
      return;
    }
    setBusy(true);
    try {
      setMessage("正在检查远端版本……");
      const fileUrl = `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`;
      const latest = await githubJson<{ sha: string }>(
        `${fileUrl}?ref=${TRACKING_BRANCH}`,
        token.trim(),
      );
      if (latest.sha !== remoteSha) {
        throw new Error("远端配置已被其他提交修改。请先点击“重新载入”，再合并本地修改。");
      }
      const normalized = normalizeTrackingConfig(config);
      const result = await githubJson<{
        content?: { sha?: string };
        commit?: { sha?: string };
      }>(fileUrl, token.trim(), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "config: update technology tracking from website",
          content: encodeBase64(`${JSON.stringify(normalized, null, 2)}\n`),
          sha: remoteSha,
          branch: TRACKING_BRANCH,
        }),
      });
      setConfig(normalized);
      setRemoteSha(result.content?.sha ?? remoteSha);
      const commit = result.commit?.sha?.slice(0, 8) ?? "已创建";
      setMessage(`配置已提交（${commit}）。Actions 将自动刷新爬虫数据和网站。`, "success");
    } catch (error) {
      setMessage(`同步失败：${error instanceof Error ? error.message : String(error)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  function addTrack() {
    const name = newTrackName.trim();
    if (!name) return;
    const base = slugifyTrack(name);
    let slug = base;
    let suffix = 2;
    while (config.tracks.some((item) => item.slug === slug)) {
      slug = `${base}-${suffix}`;
      suffix += 1;
    }
    update({
      ...config,
      tracks: [
        ...config.tracks,
        {
          slug,
          name,
          enabled: true,
          custom: true,
          keywords: [],
          people: [],
          sampleCompanies: [],
        },
      ],
    });
    setActive(config.tracks.length);
    setNewTrackName("");
  }

  function removeTrack() {
    if (!track) return;
    update({
      ...config,
      tracks: config.tracks.filter((_, index) => index !== active),
      sources: config.sources.map((source) =>
        source.sector === track.name ? { ...source, sector: "AI / AGI" } : source,
      ),
    });
  }

  function toggleTrack() {
    if (!track) return;
    update({
      ...config,
      tracks: config.tracks.map((item, index) =>
        index === active ? { ...item, enabled: !item.enabled } : item,
      ),
    });
  }

  function addListItem(field: ListField) {
    const value = listInputs[field].trim();
    if (!track || !value) return;
    update({
      ...config,
      tracks: config.tracks.map((item, index) =>
        index === active ? { ...item, [field]: [...item[field], value] } : item,
      ),
    });
    setListInputs((current) => ({ ...current, [field]: "" }));
  }

  function removeListItem(field: ListField, value: string) {
    update({
      ...config,
      tracks: config.tracks.map((item, index) =>
        index === active
          ? { ...item, [field]: item[field].filter((entry) => entry !== value) }
          : item,
      ),
    });
  }

  function addSource() {
    const draft = sourceDraft;
    if (!draft.name.trim()) {
      setMessage("信息源名称不能为空。", "error");
      return;
    }
    if (draft.sourceType !== "sec" && !/^https?:\/\//i.test(draft.url.trim())) {
      setMessage("RSS 或公司官网来源必须填写完整的 http(s) URL。", "error");
      return;
    }
    if (draft.sourceType === "sec" && !draft.ticker.trim()) {
      setMessage("SEC 来源必须填写股票代码。", "error");
      return;
    }
    const base = `source-${slugifyTrack(draft.name)}`;
    let id = base;
    let suffix = 2;
    while (config.sources.some((source) => source.id === id)) {
      id = `${base}-${suffix}`;
      suffix += 1;
    }
    const source: TrackingSource = {
      id,
      name: draft.name.trim(),
      url:
        draft.sourceType === "sec" && !draft.url.trim()
          ? "https://www.sec.gov/edgar/search/"
          : draft.url.trim(),
      sourceType: draft.sourceType,
      region: draft.region,
      sector: draft.sector || enabledTracks[0]?.name || "AI / AGI",
      company: draft.company.trim() || draft.name.trim(),
      ticker: draft.ticker.trim().toUpperCase(),
      keywords: draft.keywords
        .split(/[,，\n]/)
        .map((value) => value.trim())
        .filter(Boolean),
      enabled: true,
    };
    update({ ...config, sources: [...config.sources, source] });
    setSourceDraft({
      ...EMPTY_SOURCE,
      sector: enabledTracks[0]?.name || "AI / AGI",
    });
  }

  function toggleSource(id: string) {
    update({
      ...config,
      sources: config.sources.map((source) =>
        source.id === id ? { ...source, enabled: !source.enabled } : source,
      ),
    });
  }

  function removeSource(id: string) {
    update({
      ...config,
      sources: config.sources.filter((source) => source.id !== id),
    });
  }

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <div>
          <p className="eyebrow">GITHUB-BACKED CONFIGURATION</p>
          <h1>新兴科技追踪管理</h1>
          <p>
            在前端增删赛道、关键词、人物、样本公司和上市公司信息源。同步后直接修改仓库中的
            <code> {TRACKING_CONFIG_PATH}</code>，并触发自动爬取与部署。
          </p>
        </div>
        <div className={styles.auth}>
          <label htmlFor="github-token">Fine-grained GitHub Token</label>
          <div className={styles.authRow}>
            <input
              id="github-token"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="仅需该仓库 Contents: Read and write"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
            <button className={styles.secondary} disabled={busy} onClick={loadFromGithub}>
              {connected ? "重新载入" : "连接 GitHub"}
            </button>
          </div>
          <p className={styles.security}>
            Token 只保存在当前页面内存中，不写入 localStorage、配置文件或网站构建产物。页面刷新后自动清除。
          </p>
          <p className={styles.status} data-kind={statusKind} aria-live="polite">
            {status}
          </p>
        </div>
      </section>

      <div className={styles.grid}>
        <section className={styles.card}>
          <div className={styles.sectionHeader}>
            <div>
              <p className="section-index">TRACKS</p>
              <h2>赛道列表</h2>
            </div>
            <span className={styles.muted}>{config.tracks.length} 个</span>
          </div>
          <div className={styles.trackList}>
            {config.tracks.map((item, index) => (
              <button
                className={styles.trackTab}
                data-active={index === active}
                key={item.slug}
                onClick={() => setActive(index)}
              >
                <span>{item.name}</span>
                <span>{item.enabled ? "启用" : "停用"}</span>
              </button>
            ))}
            {!config.tracks.length && <p className={styles.empty}>当前没有赛道。</p>}
          </div>
          <div className={styles.inlineForm}>
            <input
              value={newTrackName}
              onChange={(event) => setNewTrackName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") addTrack();
              }}
              placeholder="新增赛道名称"
            />
            <button className={styles.button} onClick={addTrack}>添加</button>
          </div>
        </section>

        <section className={styles.card}>
          {track ? (
            <>
              <div className={styles.trackHeader}>
                <div>
                  <p className="section-index">TRACK DETAIL</p>
                  <h2>{track.name}</h2>
                  <p className={styles.muted}>slug: {track.slug}</p>
                </div>
                <div className={styles.actions}>
                  <button className={styles.toggle} onClick={toggleTrack}>
                    {track.enabled ? "停用赛道" : "启用赛道"}
                  </button>
                  <button className={styles.danger} onClick={removeTrack}>删除赛道</button>
                </div>
              </div>
              <div className={styles.trackSections}>
                {LIST_FIELDS.map((field) => (
                  <div className={styles.listEditor} key={field}>
                    <h3>{LABELS[field].title}</h3>
                    <p className={styles.help}>{LABELS[field].help}</p>
                    <div className={styles.tags}>
                      {track[field].map((value) => (
                        <button
                          className={styles.tag}
                          key={value}
                          title="点击删除"
                          onClick={() => removeListItem(field, value)}
                        >
                          {value} ×
                        </button>
                      ))}
                      {!track[field].length && <span className={styles.empty}>暂无条目</span>}
                    </div>
                    <div className={styles.inlineForm}>
                      <input
                        value={listInputs[field]}
                        onChange={(event) =>
                          setListInputs((current) => ({
                            ...current,
                            [field]: event.target.value,
                          }))
                        }
                        onKeyDown={(event) => {
                          if (event.key === "Enter") addListItem(field);
                        }}
                        placeholder={LABELS[field].placeholder}
                      />
                      <button className={styles.secondary} onClick={() => addListItem(field)}>
                        添加
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <p className={styles.empty}>先在左侧添加一个赛道。</p>
          )}
        </section>
      </div>

      <section className={styles.card}>
        <div className={styles.sectionHeader}>
          <div>
            <p className="section-index">LISTED-COMPANY SOURCES</p>
            <h2>上市公司搜索与披露来源</h2>
          </div>
          <span className={styles.muted}>{config.sources.length} 个</span>
        </div>
        <div className={styles.sourceForm}>
          <label>
            来源名称
            <input
              value={sourceDraft.name}
              onChange={(event) => setSourceDraft({ ...sourceDraft, name: event.target.value })}
              placeholder="例如：Example Corp IR"
            />
          </label>
          <label>
            来源类型
            <select
              value={sourceDraft.sourceType}
              onChange={(event) =>
                setSourceDraft({
                  ...sourceDraft,
                  sourceType: event.target.value as TrackingSourceType,
                })
              }
            >
              <option value="listing-search">公司官网 / IR 搜索</option>
              <option value="rss">RSS / Atom</option>
              <option value="sec">SEC EDGAR</option>
            </select>
          </label>
          <label>
            公司名称
            <input
              value={sourceDraft.company}
              onChange={(event) => setSourceDraft({ ...sourceDraft, company: event.target.value })}
              placeholder="公司正式名称"
            />
          </label>
          <label>
            股票代码
            <input
              value={sourceDraft.ticker}
              onChange={(event) => setSourceDraft({ ...sourceDraft, ticker: event.target.value })}
              placeholder="例如：NASDAQ: EXM 或 EXM"
            />
          </label>
          <label>
            所属赛道
            <select
              value={sourceDraft.sector}
              onChange={(event) => setSourceDraft({ ...sourceDraft, sector: event.target.value })}
            >
              {(enabledTracks.length ? enabledTracks : config.tracks).map((item) => (
                <option value={item.name} key={item.slug}>{item.name}</option>
              ))}
            </select>
          </label>
          <label>
            地区
            <select
              value={sourceDraft.region}
              onChange={(event) =>
                setSourceDraft({ ...sourceDraft, region: event.target.value as TrackingRegion })
              }
            >
              <option value="中国">中国</option>
              <option value="美国">美国</option>
              <option value="全球">全球</option>
            </select>
          </label>
          <label className={styles.wide}>
            官网、IR 或 RSS 地址
            <input
              value={sourceDraft.url}
              onChange={(event) => setSourceDraft({ ...sourceDraft, url: event.target.value })}
              placeholder={
                sourceDraft.sourceType === "sec"
                  ? "SEC 类型可留空，系统使用 EDGAR"
                  : "https://example.com/investors/news"
              }
            />
          </label>
          <label className={styles.wide}>
            附加关键词（逗号分隔）
            <input
              value={sourceDraft.keywords}
              onChange={(event) =>
                setSourceDraft({ ...sourceDraft, keywords: event.target.value })
              }
              placeholder="IPO, earnings, 产品名称"
            />
          </label>
          <div className={styles.wide}>
            <button className={styles.button} onClick={addSource}>添加信息源</button>
          </div>
        </div>

        <div className={styles.sourceList}>
          {config.sources.map((source) => (
            <article className={styles.sourceItem} data-disabled={!source.enabled} key={source.id}>
              <div className={styles.sectionHeader}>
                <div>
                  <strong>{source.name}</strong>
                  <div className={styles.sourceMeta}>
                    {source.sourceType} · {source.region} · {source.sector}
                    {source.ticker ? ` · ${source.ticker}` : ""}
                  </div>
                </div>
                <div className={styles.sourceActions}>
                  <button className={styles.secondary} onClick={() => toggleSource(source.id)}>
                    {source.enabled ? "停用" : "启用"}
                  </button>
                  <button className={styles.danger} onClick={() => removeSource(source.id)}>
                    删除
                  </button>
                </div>
              </div>
              <span>{source.url}</span>
              {source.keywords.length > 0 && (
                <span className={styles.sourceMeta}>关键词：{source.keywords.join(" / ")}</span>
              )}
            </article>
          ))}
          {!config.sources.length && (
            <p className={styles.empty}>尚未添加自定义上市公司来源。</p>
          )}
        </div>
      </section>

      <section className={styles.card}>
        <div className={styles.sectionHeader}>
          <div>
            <p className="section-index">PUBLISH</p>
            <h2>写入仓库并启动刷新</h2>
          </div>
          <span className={styles.muted}>{connected ? `已连接 ${username}` : "未连接"}</span>
        </div>
        <p className={styles.help}>
          同步会创建一次 main 分支 commit。配置文件变化将触发 Refresh public intelligence，随后 Pages 自动发布最新数据。
        </p>
        <div className={styles.actions}>
          <button className={styles.button} disabled={busy || !connected} onClick={syncGithub}>
            同步到 GitHub 后端
          </button>
          <button className={styles.secondary} disabled={busy || !token.trim()} onClick={loadFromGithub}>
            放弃本地修改并重新载入
          </button>
        </div>
      </section>
    </div>
  );
}
