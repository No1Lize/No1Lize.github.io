"use client";

import type { FormEvent } from "react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ipoCompanies } from "@/lib/catalog-data";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
  cloneTrackingConfig,
  normalizeTrackingConfig,
  slugifyTrack,
  type TrackingListedCompany,
  type TrackingMarket,
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
type SaveMode = "auto" | "manual";

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

type ListedDraft = {
  name: string;
  ticker: string;
  market: TrackingMarket;
  sector: string;
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

const EMPTY_LISTED: ListedDraft = {
  name: "",
  ticker: "",
  market: "美股",
  sector: "AI / AGI",
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

function disclosureSource(company: TrackingListedCompany): TrackingSource {
  const isUs = company.market === "美股";
  const url = isUs
    ? "https://www.sec.gov/edgar/search/"
    : company.market === "港股"
      ? "https://www1.hkexnews.hk/search/titlesearch.xhtml?lang=zh"
      : "https://www.cninfo.com.cn/new/index";
  return {
    id: `listed-source-${company.id}`,
    name: `${company.name} 公告披露`,
    url,
    sourceType: isUs ? "sec" : "listing-search",
    region: isUs ? "美国" : "中国",
    sector: company.sector,
    company: company.name,
    ticker: company.ticker,
    keywords: [company.name, company.ticker],
    enabled: company.enabled,
    listedCompanyId: company.id,
  };
}

export function UserTrackingPanel({ initial }: { initial: UserTrackingConfig }) {
  const [config, setConfig] = useState(() => cloneTrackingConfig(initial));
  const [token, setToken] = useState("");
  const [username, setUsername] = useState("");
  const [remoteSha, setRemoteSha] = useState("");
  const [status, setStatus] = useState("请输入仓库专用 Token 以进入管理后台。");
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(0);
  const [newTrackName, setNewTrackName] = useState("");
  const [listInputs, setListInputs] = useState<Record<ListField, string>>({
    keywords: "",
    people: "",
    sampleCompanies: "",
  });
  const [listedDraft, setListedDraft] = useState<ListedDraft>(EMPTY_LISTED);
  const [sourceDraft, setSourceDraft] = useState<SourceDraft>(EMPTY_SOURCE);
  const remoteShaRef = useRef("");
  const saveQueueRef = useRef<Promise<void>>(Promise.resolve());

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

  function setMessage(message: string, kind: StatusKind = "neutral") {
    setStatus(message);
    setStatusKind(kind);
  }

  async function persistConfig(next: UserTrackingConfig, mode: SaveMode) {
    const cleanToken = token.trim();
    const currentSha = remoteShaRef.current;
    if (!username || !cleanToken || !currentSha) {
      setMessage("修改尚未保存：管理员连接已失效。", "error");
      return;
    }

    setBusy(true);
    try {
      const fileUrl = `${API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`;
      const latest = await githubJson<{ sha: string }>(
        `${fileUrl}?ref=${TRACKING_BRANCH}`,
        cleanToken,
      );
      if (latest.sha !== currentSha) {
        throw new Error("远端配置已变化，请重新载入后再操作。 ");
      }

      const result = await githubJson<{
        content?: { sha?: string };
        commit?: { sha?: string };
      }>(fileUrl, cleanToken, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "config: update tracking from website admin",
          content: encodeBase64(`${JSON.stringify(next, null, 2)}\n`),
          sha: currentSha,
          branch: TRACKING_BRANCH,
        }),
      });

      const nextSha = result.content?.sha;
      if (!nextSha) throw new Error("GitHub 未返回新的配置文件 SHA。 ");
      remoteShaRef.current = nextSha;
      setRemoteSha(nextSha);
      setConfig(next);
      const commit = result.commit?.sha?.slice(0, 8) ?? "已创建";
      setMessage(
        `${mode === "auto" ? "已自动同步" : "已同步"}（${commit}），部署将在仓库工作流中继续。`,
        "success",
      );
    } catch (error) {
      setMessage(`同步失败：${error instanceof Error ? error.message : String(error)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  function enqueueSave(next: UserTrackingConfig, mode: SaveMode = "auto") {
    const normalized = normalizeTrackingConfig(next);
    setConfig(normalized);
    if (!connected || !token.trim() || !remoteShaRef.current) {
      setMessage("管理员连接已失效，修改尚未写入仓库。", "error");
      return Promise.resolve();
    }
    setMessage(mode === "auto" ? "正在自动同步到 GitHub……" : "正在同步到 GitHub……");
    saveQueueRef.current = saveQueueRef.current.then(() => persistConfig(normalized, mode));
    return saveQueueRef.current;
  }

  function update(next: UserTrackingConfig) {
    void enqueueSave(next, "auto");
  }

  async function loadFromGithub() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setMessage("请先输入 Fine-grained Token。", "error");
      return;
    }
    setBusy(true);
    try {
      setMessage("正在验证管理员身份并读取远端配置……");
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
      remoteShaRef.current = file.sha;
      setRemoteSha(file.sha);
      setUsername(user.login);
      setActive(0);
      setMessage(`管理员 ${user.login} 已登录。后续操作会自动提交到 main。`, "success");
    } catch (error) {
      setUsername("");
      remoteShaRef.current = "";
      setRemoteSha("");
      setMessage(`登录失败：${error instanceof Error ? error.message : String(error)}`, "error");
    } finally {
      setBusy(false);
    }
  }

  function disconnect() {
    setUsername("");
    setRemoteSha("");
    remoteShaRef.current = "";
    setToken("");
    setConfig(cloneTrackingConfig(initial));
    setMessage("管理员已退出，Token 已从页面内存清除。", "neutral");
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
        { slug, name, enabled: true, custom: true, keywords: [], people: [], sampleCompanies: [] },
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
      listedCompanies: config.listedCompanies.map((company) =>
        company.sector === track.name ? { ...company, sector: "未分类" } : company,
      ),
      sources: config.sources.map((source) =>
        source.sector === track.name ? { ...source, sector: "未分类" } : source,
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
    if (!track || !value || track[field].includes(value)) return;
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

  function addListedCompany(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = listedDraft.name.trim();
    const ticker = listedDraft.ticker.trim().toUpperCase().replace(/\s+/g, "");
    if (!name || !ticker) {
      setMessage("请填写上市公司名称和股票代码。", "error");
      return;
    }

    const catalog = ipoCompanies.find(
      (company) => company.market === listedDraft.market && company.ticker.toUpperCase() === ticker,
    );
    const existing = config.listedCompanies.find(
      (company) => company.market === listedDraft.market && company.ticker === ticker,
    );
    const id = existing?.id ?? (catalog ? `catalog-${catalog.slug}` : `listed-${listedDraft.market}-${slugifyTrack(ticker)}`);
    const company: TrackingListedCompany = {
      id,
      name: catalog?.name ?? name,
      ticker,
      market: listedDraft.market,
      sector: listedDraft.sector || catalog?.sector || "未分类",
      enabled: true,
      custom: !catalog,
      ...(catalog ? { catalogSlug: catalog.slug } : {}),
    };
    const listedCompanies = existing
      ? config.listedCompanies.map((item) => (item.id === existing.id ? company : item))
      : [...config.listedCompanies, company];
    const linkedSource = disclosureSource(company);
    const sources = config.sources.some((source) => source.listedCompanyId === id)
      ? config.sources.map((source) =>
          source.listedCompanyId === id ? { ...linkedSource, id: source.id } : source,
        )
      : [...config.sources, linkedSource];

    update({ ...config, listedCompanies, sources });
    setListedDraft({ ...EMPTY_LISTED, sector: enabledTracks[0]?.name || "未分类" });
  }

  function toggleListedCompany(id: string) {
    const target = config.listedCompanies.find((company) => company.id === id);
    if (!target) return;
    const enabled = !target.enabled;
    update({
      ...config,
      listedCompanies: config.listedCompanies.map((company) =>
        company.id === id ? { ...company, enabled } : company,
      ),
      sources: config.sources.map((source) =>
        source.listedCompanyId === id ? { ...source, enabled } : source,
      ),
    });
  }

  function removeListedCompany(id: string) {
    update({
      ...config,
      listedCompanies: config.listedCompanies.filter((company) => company.id !== id),
      sources: config.sources.filter((source) => source.listedCompanyId !== id),
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
      sector: draft.sector || enabledTracks[0]?.name || "未分类",
      company: draft.company.trim() || draft.name.trim(),
      ticker: draft.ticker.trim().toUpperCase(),
      keywords: draft.keywords.split(/[,，\n]/).map((value) => value.trim()).filter(Boolean),
      enabled: true,
    };
    update({ ...config, sources: [...config.sources, source] });
    setSourceDraft({ ...EMPTY_SOURCE, sector: enabledTracks[0]?.name || "未分类" });
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
    update({ ...config, sources: config.sources.filter((source) => source.id !== id) });
  }

  return (
    <div className={styles.shell}>
      <section className={styles.hero}>
        <div>
          <p className="eyebrow">ADMIN CONFIGURATION</p>
          <h1>网站追踪管理</h1>
          <p>
            统一管理新兴科技赛道、上市公司关注和信息源。所有修改写入
            <code> {TRACKING_CONFIG_PATH}</code>，并由仓库工作流重新构建网站。
          </p>
        </div>
        <div className={styles.auth}>
          <label htmlFor="github-token">管理员登录</label>
          <div className={styles.authRow}>
            <input
              id="github-token"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="Fine-grained Token · Contents: Read and write"
              value={token}
              onChange={(event) => setToken(event.target.value)}
            />
            <button className={styles.secondary} disabled={busy} onClick={loadFromGithub}>
              {connected ? "重新载入" : "登录"}
            </button>
            {connected && (
              <button className={styles.danger} disabled={busy} onClick={disconnect}>退出</button>
            )}
          </div>
          <p className={styles.security}>
            Token 仅存在当前页面内存中，不写入 localStorage、仓库或构建产物；刷新或退出后清除。
          </p>
          <p className={styles.status} data-kind={statusKind} aria-live="polite">{status}</p>
        </div>
      </section>

      {!connected ? (
        <section className={styles.card}>
          <p className="section-index">ADMIN ACCESS REQUIRED</p>
          <h2>编辑功能已锁定</h2>
          <p className={styles.help}>验证仓库所有者身份后，才会显示添加、删除、启停和同步操作。</p>
        </section>
      ) : (
        <>
          <div className={styles.grid}>
            <section className={styles.card}>
              <div className={styles.sectionHeader}>
                <div><p className="section-index">TRACKS</p><h2>赛道列表</h2></div>
                <span className={styles.muted}>{config.tracks.length} 个</span>
              </div>
              <div className={styles.trackList}>
                {config.tracks.map((item, index) => (
                  <button className={styles.trackTab} data-active={index === active} key={item.slug} onClick={() => setActive(index)}>
                    <span>{item.name}</span><span>{item.enabled ? "启用" : "停用"}</span>
                  </button>
                ))}
              </div>
              <div className={styles.inlineForm}>
                <input value={newTrackName} onChange={(event) => setNewTrackName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addTrack(); }} placeholder="新增赛道名称" />
                <button className={styles.button} onClick={addTrack}>添加并同步</button>
              </div>
            </section>

            <section className={styles.card}>
              {track ? (
                <>
                  <div className={styles.trackHeader}>
                    <div><p className="section-index">TRACK DETAIL</p><h2>{track.name}</h2><p className={styles.muted}>slug: {track.slug}</p></div>
                    <div className={styles.actions}>
                      <button className={styles.toggle} onClick={toggleTrack}>{track.enabled ? "停用赛道" : "启用赛道"}</button>
                      <button className={styles.danger} onClick={removeTrack}>删除赛道</button>
                    </div>
                  </div>
                  <div className={styles.trackSections}>
                    {LIST_FIELDS.map((field) => (
                      <div className={styles.listEditor} key={field}>
                        <h3>{LABELS[field].title}</h3><p className={styles.help}>{LABELS[field].help}</p>
                        <div className={styles.tags}>
                          {track[field].map((value) => <button className={styles.tag} key={value} onClick={() => removeListItem(field, value)}>{value} ×</button>)}
                          {!track[field].length && <span className={styles.empty}>暂无条目</span>}
                        </div>
                        <div className={styles.inlineForm}>
                          <input value={listInputs[field]} onChange={(event) => setListInputs((current) => ({ ...current, [field]: event.target.value }))} onKeyDown={(event) => { if (event.key === "Enter") addListItem(field); }} placeholder={LABELS[field].placeholder} />
                          <button className={styles.secondary} onClick={() => addListItem(field)}>添加并同步</button>
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : <p className={styles.empty}>先添加一个赛道。</p>}
            </section>
          </div>

          <section className={styles.card}>
            <div className={styles.sectionHeader}>
              <div><p className="section-index">PUBLIC-MARKET WATCHLIST</p><h2>上市公司关注管理</h2></div>
              <span className={styles.muted}>{config.listedCompanies.filter((item) => item.enabled).length} / {config.listedCompanies.length} 家启用</span>
            </div>
            <p className={styles.help}>这里的启用项决定“上市跟踪”页面展示哪些公司。新增公司时会自动建立对应的监管披露来源。</p>
            <form className={styles.sourceForm} onSubmit={addListedCompany}>
              <label>公司名称<input value={listedDraft.name} onChange={(event) => setListedDraft({ ...listedDraft, name: event.target.value })} placeholder="例如：英伟达" /></label>
              <label>股票代码<input value={listedDraft.ticker} onChange={(event) => setListedDraft({ ...listedDraft, ticker: event.target.value })} placeholder="例如：NVDA" /></label>
              <label>市场<select value={listedDraft.market} onChange={(event) => setListedDraft({ ...listedDraft, market: event.target.value as TrackingMarket })}><option value="A股">A股</option><option value="港股">港股</option><option value="美股">美股</option></select></label>
              <label>所属赛道<select value={listedDraft.sector} onChange={(event) => setListedDraft({ ...listedDraft, sector: event.target.value })}>{(enabledTracks.length ? enabledTracks : config.tracks).map((item) => <option value={item.name} key={item.slug}>{item.name}</option>)}<option value="未分类">未分类</option></select></label>
              <div className={styles.wide}><button className={styles.button} type="submit">添加关注并自动同步</button></div>
            </form>
            <div className={styles.sourceList}>
              {config.listedCompanies.map((company) => (
                <article className={styles.sourceItem} data-disabled={!company.enabled} key={company.id}>
                  <div className={styles.sectionHeader}>
                    <div><strong>{company.name}</strong><div className={styles.sourceMeta}>{company.market} · {company.ticker} · {company.sector}{company.custom ? " · 自定义" : " · 已有档案"}</div></div>
                    <div className={styles.sourceActions}>
                      <button className={styles.secondary} onClick={() => toggleListedCompany(company.id)}>{company.enabled ? "停用" : "启用"}</button>
                      <button className={styles.danger} onClick={() => removeListedCompany(company.id)}>删除</button>
                    </div>
                  </div>
                </article>
              ))}
              {!config.listedCompanies.length && <p className={styles.empty}>当前没有关注的上市公司。</p>}
            </div>
          </section>

          <section className={styles.card}>
            <div className={styles.sectionHeader}>
              <div><p className="section-index">CUSTOM SOURCES</p><h2>补充信息源</h2></div>
              <span className={styles.muted}>{config.sources.length} 个</span>
            </div>
            <div className={styles.sourceForm}>
              <label>来源名称<input value={sourceDraft.name} onChange={(event) => setSourceDraft({ ...sourceDraft, name: event.target.value })} placeholder="例如：Example Corp IR" /></label>
              <label>来源类型<select value={sourceDraft.sourceType} onChange={(event) => setSourceDraft({ ...sourceDraft, sourceType: event.target.value as TrackingSourceType })}><option value="listing-search">公司官网 / IR 搜索</option><option value="rss">RSS / Atom</option><option value="sec">SEC EDGAR</option></select></label>
              <label>公司名称<input value={sourceDraft.company} onChange={(event) => setSourceDraft({ ...sourceDraft, company: event.target.value })} /></label>
              <label>股票代码<input value={sourceDraft.ticker} onChange={(event) => setSourceDraft({ ...sourceDraft, ticker: event.target.value })} /></label>
              <label>所属赛道<select value={sourceDraft.sector} onChange={(event) => setSourceDraft({ ...sourceDraft, sector: event.target.value })}>{(enabledTracks.length ? enabledTracks : config.tracks).map((item) => <option value={item.name} key={item.slug}>{item.name}</option>)}<option value="未分类">未分类</option></select></label>
              <label>地区<select value={sourceDraft.region} onChange={(event) => setSourceDraft({ ...sourceDraft, region: event.target.value as TrackingRegion })}><option value="中国">中国</option><option value="美国">美国</option><option value="全球">全球</option></select></label>
              <label className={styles.wide}>官网、IR 或 RSS 地址<input value={sourceDraft.url} onChange={(event) => setSourceDraft({ ...sourceDraft, url: event.target.value })} placeholder={sourceDraft.sourceType === "sec" ? "SEC 类型可留空" : "https://example.com/investors/news"} /></label>
              <label className={styles.wide}>附加关键词<input value={sourceDraft.keywords} onChange={(event) => setSourceDraft({ ...sourceDraft, keywords: event.target.value })} placeholder="逗号分隔" /></label>
              <div className={styles.wide}><button className={styles.button} onClick={addSource}>添加信息源并自动同步</button></div>
            </div>
            <div className={styles.sourceList}>
              {config.sources.map((source) => (
                <article className={styles.sourceItem} data-disabled={!source.enabled} key={source.id}>
                  <div className={styles.sectionHeader}>
                    <div><strong>{source.name}</strong><div className={styles.sourceMeta}>{source.sourceType} · {source.region} · {source.sector}{source.ticker ? ` · ${source.ticker}` : ""}{source.listedCompanyId ? " · 上市公司关联源" : ""}</div></div>
                    <div className={styles.sourceActions}><button className={styles.secondary} onClick={() => toggleSource(source.id)}>{source.enabled ? "停用" : "启用"}</button><button className={styles.danger} onClick={() => removeSource(source.id)}>删除</button></div>
                  </div>
                  <span>{source.url}</span>
                </article>
              ))}
            </div>
          </section>

          <section className={styles.card}>
            <div className={styles.sectionHeader}><div><p className="section-index">SYNC STATUS</p><h2>GitHub 自动同步</h2></div><span className={styles.muted}>已连接 {username}</span></div>
            <p className={styles.help}>每次添加、删除、启用或停用都会写入 main 分支。手动按钮仅用于重试。</p>
            <div className={styles.actions}><button className={styles.button} disabled={busy} onClick={() => void enqueueSave(config, "manual")}>立即重试同步</button><button className={styles.secondary} disabled={busy} onClick={loadFromGithub}>放弃本地状态并重新载入</button></div>
          </section>
        </>
      )}
    </div>
  );
}
