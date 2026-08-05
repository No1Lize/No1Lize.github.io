"use client";

import {
  Building2,
  Cpu,
  ExternalLink,
  LoaderCircle,
  Plus,
  UserRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  TRACKING_CAPTURE_CHANGED_EVENT,
  TRACKING_ADMIN_TOKEN_SESSION_KEY,
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
import styles from "./intelligence-tracking-capture-controls.module.css";

type CapturePlacement = "event" | "feed" | "corner" | "cornerArrow";

type CaptureItem = TrackingCaptureSource & {
  company: string;
  sectors: string[];
  keywords: string[];
};

type CaptureMount = {
  host: HTMLElement;
  element: HTMLElement;
  item: CaptureItem;
  key: string;
  placement: CapturePlacement;
};

type EntityRow = TrackingCaptureEntityDraft & { id: string };

type StatusKind = "neutral" | "success" | "error";

const CHANNEL_LABELS: Record<string, string> = {
  technology: "新兴科技",
  companies: "创业案例",
  institutions: "投资机构",
  ipo: "上市跟踪",
  reports: "研究报告",
  people: "人物研究",
};

const RESEARCH_REASON_OPTIONS = [
  "融资机会",
  "技术突破",
  "商业模式创新",
  "市场竞争",
  "IPO可能",
  "监管变化",
  "个人研究兴趣",
] as const;

const LATIN_STOPWORDS = new Set([
  "AI",
  "IPO",
  "CEO",
  "CTO",
  "Inc",
  "Ltd",
  "LLC",
  "US",
  "USD",
  "China",
  "Global",
]);

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function dataValue(element: HTMLElement, suffix: string): string {
  const key = `intelligence${suffix}`;
  return cleanText((element.dataset as Record<string, string | undefined>)[key]);
}

function listText(value: string): string[] {
  return value
    .split(/[|｜、,，]/u)
    .map(cleanText)
    .filter(Boolean);
}

function hrefFrom(anchor: HTMLAnchorElement | null): string {
  if (!anchor) return "";
  const raw = cleanText(anchor.getAttribute("href"));
  if (raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return cleanText(anchor.href || raw);
}

function hrefFromRow(row: HTMLElement): string {
  const explicit = dataValue(row, "Href");
  if (explicit) return explicit;
  if (row instanceof HTMLAnchorElement) return hrefFrom(row);
  return hrefFrom(
    row.querySelector<HTMLAnchorElement>("a.source-link[href]") ||
      row.querySelector<HTMLAnchorElement>("a[data-intelligence-link][href]") ||
      row.querySelector<HTMLAnchorElement>("a[target='_blank'][href]") ||
      row.querySelector<HTMLAnchorElement>("a[href]"),
  );
}

function channelFromPath(): { channel: string; label: string } {
  if (typeof window === "undefined") return { channel: "companies", label: "创业案例" };
  const path = window.location.pathname;
  const key = Object.keys(CHANNEL_LABELS).find((candidate) => path.startsWith(`/${candidate}`));
  return key
    ? { channel: key, label: CHANNEL_LABELS[key] }
    : { channel: "companies", label: "创业案例" };
}

function inferChannel(eventType: string, context: string): { channel: string; label: string } {
  const explicit = channelFromPath();
  if (explicit.channel !== "companies" || window.location.pathname !== "/") return explicit;
  const combined = `${eventType} ${context}`;
  if (/人物|采访|演讲|观点|创始人/.test(combined)) return { channel: "people", label: "人物研究" };
  if (/研报|报告|政策|PDF|研究材料/.test(combined)) return { channel: "reports", label: "研究报告" };
  if (/IPO|上市|招股|财报|交易所/.test(combined)) return { channel: "ipo", label: "上市跟踪" };
  if (/融资|投资|并购|基金|资本|机构/.test(combined)) return { channel: "institutions", label: "投资机构" };
  if (/技术|论文|模型|AI|芯片|机器人|产品/.test(combined)) return { channel: "technology", label: "新兴科技" };
  return explicit;
}

function captureItemForRow(row: HTMLElement): CaptureItem | null {
  const href = hrefFromRow(row);
  const title =
    dataValue(row, "Title") ||
    cleanText(row.querySelector<HTMLElement>("[data-intelligence-title], h3, h2, strong")?.textContent);
  if (!href || !title) return null;

  const summary =
    dataValue(row, "Summary") ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-summary], .event-main > p, [class*='summary'], p",
      )?.textContent,
    );
  const eventType =
    dataValue(row, "Type") ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-type], .event-tags span, [class*='feedTag'], [class*='meta'] span",
      )?.textContent,
    ) ||
    "公开材料";
  const context =
    dataValue(row, "Context") ||
    cleanText(row.querySelector<HTMLElement>("[data-intelligence-context], [class*='context']")?.textContent);
  const explicitChannel = dataValue(row, "Channel");
  const inferred = explicitChannel && CHANNEL_LABELS[explicitChannel]
    ? { channel: explicitChannel, label: dataValue(row, "ChannelLabel") || CHANNEL_LABELS[explicitChannel] }
    : inferChannel(eventType, `${context} ${title}`);
  const sourceName =
    dataValue(row, "Source") ||
    cleanText(
      row.querySelector<HTMLElement>(
        "[data-intelligence-source], .source-link, [class*='source'], small",
      )?.textContent,
    ) ||
    "公开信源";
  const visibleTags = [...row.querySelectorAll<HTMLElement>(
    "[data-intelligence-tag], .event-tags span, [class*='feedTag'], [class*='meta'] span",
  )]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const sectors = [
    ...listText(dataValue(row, "Sector")),
    ...visibleTags.filter((tag) => userTrackingConfig.tracks.some((track) => track.name === tag)),
  ];
  const keywords = [
    ...listText(dataValue(row, "Keywords")),
    eventType,
    ...visibleTags,
  ].filter((value, index, rows) => value && rows.indexOf(value) === index);
  const company = dataValue(row, "Company");
  const articleId =
    dataValue(row, "Id") ||
    `article-${stableTrackingCaptureHash(`${title}|${href}`)}`;

  return {
    articleId,
    title,
    url: href,
    summary,
    sourceName,
    channel: inferred.channel,
    channelLabel: inferred.label,
    eventType,
    company,
    sectors: [...new Set(sectors)],
    keywords,
  };
}

function collectCandidateRows(): HTMLElement[] {
  const rows = new Set<HTMLElement>();
  const add = (selector: string) => {
    document.querySelectorAll<HTMLElement>(selector).forEach((row) => rows.add(row));
  };
  add(".event-row");
  add("[data-intelligence-item]");
  add(".headlines-column a[class*='feedRow']");
  add(".side-column a[class*='feedRow']");
  add(".material-list > a");
  add("a.source-card[href]");
  add("a[class*='eventCard'][href]");
  add(".market-news-item[href]");
  return [...rows];
}

function placementFor(row: HTMLElement): CapturePlacement {
  if (row.matches(".event-row")) return "event";
  if (row.matches(".headlines-column a[class*='feedRow'], .side-column a[class*='feedRow']")) {
    return "feed";
  }
  return row.querySelector("svg, [class*='arrow']") ? "cornerArrow" : "corner";
}

function suggestCompanyNames(item: CaptureItem): string[] {
  if (item.company) return [item.company];
  const matches = `${item.title} ${item.summary}`.match(/\b[A-Z][A-Za-z0-9.-]{2,}\b/g) ?? [];
  return [...new Set(matches.filter((value) => !LATIN_STOPWORDS.has(value)))].slice(0, 3);
}

function makeEntityRow(entityType: TrackingCaptureEntityType, name = ""): EntityRow {
  return {
    id: `entity-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    entityType,
    name,
  };
}

function defaultEntityRows(item: CaptureItem): EntityRow[] {
  const companies = suggestCompanyNames(item);
  return companies.length
    ? companies.map((name) => makeEntityRow("company", name))
    : [makeEntityRow("company")];
}

function defaultTrackSlugs(item: CaptureItem, config: UserTrackingConfig): string[] {
  const exact = config.tracks
    .filter((track) => item.sectors.includes(track.name))
    .map((track) => track.slug);
  if (exact.length) return exact;
  const keywordMatch = config.tracks.find((track) =>
    item.keywords.some((keyword) =>
      track.keywords.some((tracked) => tracked.toLocaleLowerCase("zh-CN") === keyword.toLocaleLowerCase("zh-CN")),
    ),
  );
  return keywordMatch
    ? [keywordMatch.slug]
    : config.tracks.find((track) => track.enabled)
      ? [config.tracks.find((track) => track.enabled)!.slug]
      : [];
}

function TrackCaptureButton({ item, onOpen }: { item: CaptureItem; onOpen: () => void }) {
  return (
    <button
      type="button"
      className={styles.captureButton}
      aria-label={`追踪本文中的公司、人物或技术：${item.title}`}
      title="从本文采集公司、人物或技术并加入追踪系统"
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        onOpen();
      }}
    >
      <Plus size={12} />
      <span>追踪</span>
    </button>
  );
}

function CaptureDrawer({ item, onClose }: { item: CaptureItem; onClose: () => void }) {
  const [config, setConfig] = useState(() => cloneTrackingConfig(userTrackingConfig));
  const [entities, setEntities] = useState<EntityRow[]>(() => defaultEntityRows(item));
  const [selectedTrackSlugs, setSelectedTrackSlugs] = useState<string[]>(() =>
    defaultTrackSlugs(item, userTrackingConfig),
  );
  const [newTrackName, setNewTrackName] = useState("");
  const [selectedReasons, setSelectedReasons] = useState<string[]>([]);
  const [researchNote, setResearchNote] = useState("");
  const [token, setToken] = useState(() =>
    typeof window === "undefined"
      ? ""
      : window.sessionStorage.getItem(TRACKING_ADMIN_TOKEN_SESSION_KEY) ?? "",
  );
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState("选择对象类型和目标赛道后，即可一次写入追踪配置与文章采集箱。");
  const [statusKind, setStatusKind] = useState<StatusKind>("neutral");

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previous;
    };
  }, [busy, onClose]);

  const usableEntities = useMemo(
    () => entities.filter((entity) => entity.name.trim()),
    [entities],
  );

  function addEntity(entityType: TrackingCaptureEntityType) {
    setEntities((current) => [...current, makeEntityRow(entityType)]);
  }

  function updateEntity(id: string, patch: Partial<EntityRow>) {
    setEntities((current) =>
      current.map((entity) => (entity.id === id ? { ...entity, ...patch } : entity)),
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
    setSelectedReasons((current) =>
      current.includes(reason)
        ? current.filter((candidate) => candidate !== reason)
        : [...current, reason],
    );
  }

  async function submit() {
    const cleanToken = token.trim();
    if (!cleanToken) {
      setStatus("请填写仓库 Fine-grained Token；权限需要 Contents: Read and write。 ");
      setStatusKind("error");
      return;
    }
    if (!usableEntities.length) {
      setStatus("请至少填写一个公司、人物或技术／主题。");
      setStatusKind("error");
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
        const result = applyTrackingCapture({
          config: remote.config,
          inbox: remote.inbox,
          entities: usableEntities.map(({ entityType, name }) => ({ entityType, name })),
          selectedTrackSlugs,
          newTrackName,
          reasons: selectedReasons,
          note: researchNote,
          source: item,
          capturedAt,
          capturedBy: remote.username,
        });
        try {
          const commitSha = await commitTrackingCaptureRepositoryState(cleanToken, remote, {
            config: result.config,
            inbox: result.inbox,
          });
          setConfig(result.config);
          setSelectedTrackSlugs(result.trackSlugs);
          setStatus(
            `已提交 ${result.records.length} 个追踪对象（${commitSha.slice(0, 8)}）。新增 ${result.addedCount} 项，重复 ${result.duplicateCount} 项；公司对象将进入候选审核流程。`,
          );
          setStatusKind("success");
          window.dispatchEvent(
            new CustomEvent(TRACKING_CAPTURE_CHANGED_EVENT, { detail: result.records }),
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
      setStatus(`提交失败：${error instanceof Error ? error.message : String(error)}`);
      setStatusKind("error");
    } finally {
      setBusy(false);
    }
  }

  return createPortal(
    <div className={styles.backdrop} role="presentation" onMouseDown={() => !busy && onClose()}>
      <aside
        className={styles.drawer}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tracking-capture-title"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className={styles.drawerHeader}>
          <div>
            <p>ARTICLE TRACKING CAPTURE</p>
            <h2 id="tracking-capture-title">从本文添加追踪对象</h2>
          </div>
          <button type="button" className={styles.iconButton} disabled={busy} onClick={onClose}>
            <X size={18} />
            <span className="sr-only">关闭</span>
          </button>
        </header>

        <section className={styles.sourceCard}>
          <div>
            <span>{item.channelLabel} · {item.eventType}</span>
            <strong>{item.title}</strong>
            <p>{item.summary || "本文已作为人工采集证据保存。"}</p>
          </div>
          <a href={item.url} target="_blank" rel="noreferrer">
            查看原文 <ExternalLink size={13} />
          </a>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <div>
              <p>01 / ENTITIES</p>
              <h3>公司、人物和技术／主题</h3>
            </div>
            <span>{usableEntities.length} 项</span>
          </div>
          <div className={styles.entityList}>
            {entities.map((entity) => (
              <div className={styles.entityRow} key={entity.id}>
                <select
                  value={entity.entityType}
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
                  onChange={(event) => updateEntity(entity.id, { name: event.target.value })}
                  placeholder={
                    entity.entityType === "company"
                      ? "例如：Polymarket、Kalshi"
                      : entity.entityType === "person"
                        ? "例如：姓名 @handle"
                        : "例如：预测市场、prediction market"
                  }
                />
                <button type="button" className={styles.removeButton} onClick={() => removeEntity(entity.id)}>
                  <X size={15} />
                </button>
              </div>
            ))}
          </div>
          <div className={styles.quickAdd}>
            <button type="button" onClick={() => addEntity("company")}>
              <Building2 size={14} /> + 公司
            </button>
            <button type="button" onClick={() => addEntity("person")}>
              <UserRound size={14} /> + 人物
            </button>
            <button type="button" onClick={() => addEntity("topic")}>
              <Cpu size={14} /> + 技术／主题
            </button>
          </div>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <div>
              <p>02 / TRACKS</p>
              <h3>加入一个或多个赛道</h3>
            </div>
            <span>{selectedTrackSlugs.length} 个已选</span>
          </div>
          <div className={styles.trackGrid}>
            {config.tracks.filter((track) => track.enabled).map((track) => (
              <label key={track.slug} data-selected={selectedTrackSlugs.includes(track.slug)}>
                <input
                  type="checkbox"
                  checked={selectedTrackSlugs.includes(track.slug)}
                  onChange={() => toggleTrack(track.slug)}
                />
                <span>{track.name}</span>
              </label>
            ))}
          </div>
          <label className={styles.newTrack}>
            新建赛道（可选）
            <input
              value={newTrackName}
              onChange={(event) => setNewTrackName(event.target.value)}
              placeholder="例如：预测市场"
            />
          </label>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <div>
              <p>03 / RESEARCH INTENT</p>
              <h3>为什么关注</h3>
            </div>
            <span>{selectedReasons.length} 个原因</span>
          </div>
          <div className={styles.reasonGrid}>
            {RESEARCH_REASON_OPTIONS.map((reason) => (
              <label key={reason} data-selected={selectedReasons.includes(reason)}>
                <input
                  type="checkbox"
                  checked={selectedReasons.includes(reason)}
                  onChange={() => toggleReason(reason)}
                />
                <span>{reason}</span>
              </label>
            ))}
          </div>
          <label className={styles.researchNote}>
            研究备注（可选）
            <textarea
              value={researchNote}
              onChange={(event) => setResearchNote(event.target.value)}
              placeholder="例如：预测市场可能成为金融科技的新基础设施，重点观察融资、牌照和监管窗口。"
            />
          </label>
        </section>

        <section className={styles.section}>
          <div className={styles.sectionHeading}>
            <div>
              <p>04 / ADMIN COMMIT</p>
              <h3>管理员同步</h3>
            </div>
          </div>
          <label className={styles.tokenField}>
            Fine-grained Token
            <input
              type="password"
              autoComplete="off"
              spellCheck={false}
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Contents: Read and write"
            />
          </label>
          <p className={styles.securityNote}>
            Token 仅保存在当前标签页 sessionStorage；提交会将追踪配置和文章采集箱原子写入同一个 GitHub commit。
          </p>
        </section>

        <footer className={styles.drawerFooter}>
          <p data-kind={statusKind} aria-live="polite">{status}</p>
          <div>
            <button type="button" className={styles.secondaryButton} disabled={busy} onClick={onClose}>
              取消
            </button>
            <button type="button" className={styles.primaryButton} disabled={busy} onClick={submit}>
              {busy ? <LoaderCircle className={styles.spinner} size={15} /> : <Plus size={15} />}
              添加并开始追踪
            </button>
          </div>
        </footer>
      </aside>
    </div>,
    document.body,
  );
}

export function IntelligenceTrackingCaptureControls() {
  const [mounts, setMounts] = useState<CaptureMount[]>([]);
  const [activeItem, setActiveItem] = useState<CaptureItem | null>(null);

  useEffect(() => {
    const registry = new Map<HTMLElement, CaptureMount>();
    let frame = 0;
    let sequence = 0;

    const removeMount = (mount: CaptureMount) => {
      mount.element.remove();
      mount.host.classList.remove(styles.cornerHost, styles.cornerSpace);
      delete mount.host.dataset.intelligenceCaptureAttached;
    };

    const publish = () => setMounts([...registry.values()]);

    const addMount = (
      host: HTMLElement,
      item: CaptureItem,
      placement: CapturePlacement,
    ): CaptureMount => {
      const element = document.createElement("span");
      const key = `${placement}:${sequence}:${item.articleId}`;
      sequence += 1;
      element.dataset.intelligenceCaptureMount = "true";
      element.className = [
        styles.mount,
        placement === "event"
          ? styles.eventMount
          : placement === "feed"
            ? styles.feedMount
            : placement === "cornerArrow"
              ? styles.cornerArrowMount
              : styles.cornerMount,
      ].join(" ");

      if (placement === "event") {
        host.querySelector<HTMLElement>(".importance")?.prepend(element);
      } else if (placement === "feed") {
        host.querySelector<HTMLElement>("[class*='feedContext']")?.appendChild(element);
      } else {
        host.classList.add(styles.cornerHost, styles.cornerSpace);
        host.appendChild(element);
      }
      host.dataset.intelligenceCaptureAttached = "true";
      return { host, element, item, key, placement };
    };

    const scan = () => {
      frame = 0;
      let changed = false;
      for (const [host, mount] of registry) {
        if (!host.isConnected || !mount.element.isConnected) {
          removeMount(mount);
          registry.delete(host);
          changed = true;
        }
      }
      for (const row of collectCandidateRows()) {
        const item = captureItemForRow(row);
        if (!item) continue;
        const placement = placementFor(row);
        const existing = registry.get(row);
        if (existing) {
          if (
            existing.item.articleId !== item.articleId ||
            existing.item.title !== item.title ||
            existing.item.url !== item.url
          ) {
            registry.set(row, { ...existing, item });
            changed = true;
          }
          continue;
        }
        const mount = addMount(row, item, placement);
        if (!mount.element.isConnected) continue;
        registry.set(row, mount);
        changed = true;
      }
      if (changed) publish();
    };

    const schedule = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(scan);
    };

    scan();
    const observer = new MutationObserver(schedule);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => {
      observer.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
      registry.forEach(removeMount);
      registry.clear();
    };
  }, []);

  return (
    <>
      {mounts.map(({ element, item, key }) =>
        createPortal(
          <TrackCaptureButton item={item} onOpen={() => setActiveItem(item)} />,
          element,
          key,
        ),
      )}
      {activeItem ? <CaptureDrawer item={activeItem} onClose={() => setActiveItem(null)} /> : null}
    </>
  );
}
