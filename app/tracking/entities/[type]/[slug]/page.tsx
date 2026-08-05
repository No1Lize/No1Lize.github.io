import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  BookmarkPlus,
  Building2,
  CircleAlert,
  Clock3,
  Cpu,
  ExternalLink,
  FileText,
  GitBranch,
  Network,
  Radar,
  Sparkles,
  Star,
  UserRound,
} from "lucide-react";
import {
  trackingResearchBrief,
  trackingResearchRelations,
} from "@/lib/tracking-entity-insights";
import {
  trackingResearchEntities,
  trackingResearchEntity,
  trackingResearchGeneratedAt,
  type TrackingResearchEntityType,
} from "@/lib/tracking-entity-research";
import styles from "./tracking-entity-detail.module.css";

const TYPE_LABELS: Record<TrackingResearchEntityType, string> = {
  company: "公司",
  person: "人物",
  topic: "技术／主题",
};

const STATE_LABELS = {
  formal: "已有正式档案",
  candidate: "候选审核中",
  tracked: "追踪中",
} as const;

const CONFIDENCE_LABELS = {
  high: "高置信证据",
  medium: "单条证据",
  contextual: "赛道上下文",
} as const;

function isEntityType(value: string): value is TrackingResearchEntityType {
  return value === "company" || value === "person" || value === "topic";
}

function displayDate(value: string) {
  if (!value) return "尚未记录";
  const match = value.match(/^\d{4}-\d{2}-\d{2}/u);
  return match?.[0] ?? value;
}

function TypeIcon({ type, size = 20 }: { type: TrackingResearchEntityType; size?: number }) {
  if (type === "company") return <Building2 size={size} aria-hidden="true" />;
  if (type === "person") return <UserRound size={size} aria-hidden="true" />;
  return <Cpu size={size} aria-hidden="true" />;
}

function AttentionStars({ level }: { level: number }) {
  return (
    <span className={styles.stars} aria-label={`${level} 星关注等级`}>
      {Array.from({ length: 5 }, (_, index) => (
        <Star
          aria-hidden="true"
          fill={index < level ? "currentColor" : "none"}
          key={index}
          size={14}
        />
      ))}
    </span>
  );
}

export function generateStaticParams() {
  return trackingResearchEntities.map((entity) => ({
    type: entity.entityType,
    slug: entity.slug,
  }));
}

export const dynamicParams = false;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ type: string; slug: string }>;
}): Promise<Metadata> {
  const { type, slug } = await params;
  const entity = isEntityType(type) ? trackingResearchEntity(type, slug) : undefined;
  return {
    title: entity ? `Research | ${entity.name} | VCIQ` : "追踪对象研究",
    description: entity?.summary ?? "公司、人物和技术主题的可追溯研究时间线。",
  };
}

export default async function TrackingEntityDetailPage({
  params,
}: {
  params: Promise<{ type: string; slug: string }>;
}) {
  const { type, slug } = await params;
  if (!isEntityType(type)) notFound();
  const entity = trackingResearchEntity(type, slug);
  if (!entity) notFound();

  const brief = trackingResearchBrief(entity);
  const relations = trackingResearchRelations(entity, 10);
  const timeline = entity.timeline.slice(0, 60);
  const firstCapture = timeline
    .filter((item) => item.origin === "manual-capture")
    .sort((left, right) => left.observedAt.localeCompare(right.observedAt))[0];

  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div>
          <Link href="/tracking/entities" className={styles.back}>
            <ArrowLeft size={15} aria-hidden="true" />追踪对象研究库
          </Link>
          <p className="eyebrow">TRACKED ENTITY RESEARCH</p>
          <div className={styles.titleRow}>
            <span data-type={entity.entityType} className={styles.typeIcon}>
              <TypeIcon type={entity.entityType} size={24} />
            </span>
            <div>
              <h1>{entity.name}</h1>
              <p>{TYPE_LABELS[entity.entityType]} · {STATE_LABELS[entity.state]}</p>
            </div>
          </div>
          <p className={styles.summary}>{entity.summary}</p>
          <div className={styles.chips}>
            {entity.trackNames.map((track) => <span key={track}>{track}</span>)}
            {entity.candidateStatus ? <span>候选状态：{entity.candidateStatus}</span> : null}
          </div>
        </div>
        <div className={styles.actions}>
          {entity.formalHref ? (
            <Link href={entity.formalHref} className={styles.primaryAction}>
              {entity.formalLabel}<ExternalLink size={14} aria-hidden="true" />
            </Link>
          ) : entity.entityType === "company" ? (
            <Link href="/tracking#company-candidate-review" className={styles.primaryAction}>
              进入候选审核<ExternalLink size={14} aria-hidden="true" />
            </Link>
          ) : null}
          <Link href="/tracking#tracking-capture-inbox" className={styles.secondaryAction}>
            查看文章采集箱
          </Link>
        </div>
      </header>

      <section className={styles.metrics} aria-label="追踪对象统计">
        <div><span><BookmarkPlus size={16} />人工发现</span><strong>{entity.captureCount}</strong></div>
        <div><span><FileText size={16} />公开动态</span><strong>{entity.articleCount}</strong></div>
        <div><span><Clock3 size={16} />首次追踪</span><strong>{displayDate(entity.firstTrackedAt)}</strong></div>
        <div><span><GitBranch size={16} />最近活动</span><strong>{displayDate(entity.lastActivityAt)}</strong></div>
      </section>

      <section className={styles.brief} aria-labelledby="automatic-research-brief">
        <header>
          <div>
            <p className="section-index">AUTOMATIC RESEARCH BRIEF</p>
            <h2 id="automatic-research-brief"><Sparkles size={19} />自动研究摘要</h2>
          </div>
          <div className={styles.attentionBadge}>
            <AttentionStars level={brief.attentionLevel} />
            <strong>{brief.attentionLabel}</strong>
          </div>
        </header>
        <div className={styles.briefLead}>
          <h3>{brief.headline}</h3>
          <p>{brief.summary}</p>
        </div>
        {brief.signals.length ? (
          <div className={styles.signalGrid}>
            {brief.signals.map((signal) => (
              <article key={signal.category}>
                <span><Radar size={14} />{signal.label}</span>
                <strong>{signal.count} 条</strong>
                <small>{displayDate(signal.latestAt)} · {signal.latestTitle}</small>
              </article>
            ))}
          </div>
        ) : null}
        <div className={styles.briefColumns}>
          <section>
            <h3><Radar size={16} />重点观察</h3>
            {brief.watchItems.length ? (
              <ul>{brief.watchItems.map((item) => <li key={item}>{item}</li>)}</ul>
            ) : (
              <p>尚未形成足够的人工原因或事件信号。</p>
            )}
          </section>
          <section>
            <h3><CircleAlert size={16} />待核问题</h3>
            {brief.openQuestions.length ? (
              <ul>{brief.openQuestions.map((item) => <li key={item}>{item}</li>)}</ul>
            ) : (
              <p>当前没有由数据缺口自动产生的待核问题。</p>
            )}
          </section>
        </div>
        <p className={styles.methodology}>{brief.methodology}</p>
      </section>

      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <section>
            <p className="section-index">WHY TRACKED</p>
            <h2>为什么关注</h2>
            <div className={styles.sidebarAttention}>
              <AttentionStars level={brief.attentionLevel} />
              <span>{brief.attentionLabel}</span>
            </div>
            {entity.reasons.length ? (
              <div className={styles.reasonList}>
                {entity.reasons.map((reason) => <span key={reason}>{reason}</span>)}
              </div>
            ) : (
              <p className={styles.muted}>尚未记录结构化关注原因。下次从文章点击“＋追踪”时可补充。</p>
            )}
            {entity.notes.length ? (
              <div className={styles.notes}>
                {entity.notes.map((note) => <p key={note}>{note}</p>)}
              </div>
            ) : null}
          </section>

          <section>
            <p className="section-index">IDENTITY</p>
            <h2>身份与追踪范围</h2>
            <dl className={styles.facts}>
              <div><dt>对象类型</dt><dd>{TYPE_LABELS[entity.entityType]}</dd></div>
              <div><dt>档案状态</dt><dd>{STATE_LABELS[entity.state]}</dd></div>
              <div><dt>关联赛道</dt><dd>{entity.trackNames.join("、") || "未分配"}</dd></div>
              <div><dt>数据快照</dt><dd>{displayDate(trackingResearchGeneratedAt)}</dd></div>
            </dl>
            {entity.aliases.length > 1 ? (
              <div className={styles.aliases}>
                <strong>别名</strong>
                <p>{entity.aliases.slice(1).join("、")}</p>
              </div>
            ) : null}
          </section>

          {firstCapture ? (
            <section>
              <p className="section-index">FIRST DISCOVERY</p>
              <h2>首次人工发现</h2>
              <a className={styles.firstSource} href={firstCapture.url} target="_blank" rel="noreferrer">
                <span>{displayDate(firstCapture.observedAt)} · {firstCapture.sourceName}</span>
                <strong>{firstCapture.title}</strong>
                <ExternalLink size={14} aria-hidden="true" />
              </a>
            </section>
          ) : null}
        </aside>

        <article className={styles.mainColumn}>
          <header className={styles.sectionHeader}>
            <div>
              <p className="section-index">RESEARCH TIMELINE</p>
              <h2>研究时间线</h2>
            </div>
            <p>按事件日期和首次发现时间倒序；“人工发现”表示该材料曾由管理员明确加入追踪。</p>
          </header>

          <div className={styles.timeline}>
            {timeline.map((item) => (
              <article className={styles.timelineItem} key={item.id}>
                <div className={styles.timelineDate}>
                  <strong>{displayDate(item.eventDate || item.observedAt)}</strong>
                  <span>{item.origin === "manual-capture" ? "人工发现" : "公开动态"}</span>
                </div>
                <div className={styles.timelineBody}>
                  <div className={styles.timelineMeta}>
                    <span>{item.eventType}</span>
                    <span>{item.sourceName}</span>
                    {item.channelLabel ? <span>{item.channelLabel}</span> : null}
                  </div>
                  <h3>{item.title}</h3>
                  <p>{item.summary || "该公开材料未保存摘要，请查看原文。"}</p>
                  {item.reasons.length ? (
                    <div className={styles.reasonList}>
                      {item.reasons.map((reason) => <span key={reason}>{reason}</span>)}
                    </div>
                  ) : null}
                  {item.note ? <blockquote>{item.note}</blockquote> : null}
                  <div className={styles.timelineFooter}>
                    {item.capturedBy ? <span>采集人：{item.capturedBy}</span> : <span>公开情报系统</span>}
                    <a href={item.url} target="_blank" rel="noreferrer">
                      查看原文<ExternalLink size={13} aria-hidden="true" />
                    </a>
                  </div>
                </div>
              </article>
            ))}
            {!timeline.length ? (
              <div className={styles.empty}>
                <FileText size={24} aria-hidden="true" />
                <strong>暂时没有可追溯公开动态</strong>
                <p>继续从主频道文章中采集，或等待下一次情报刷新。</p>
              </div>
            ) : null}
          </div>

          {relations.length ? (
            <section className={styles.relations}>
              <header className={styles.sectionHeader}>
                <div>
                  <p className="section-index">EVIDENCE RELATIONS</p>
                  <h2><Network size={19} />关系与共同赛道</h2>
                </div>
                <p>竞争、合作和共同出现必须保留原文证据；共同赛道仅表示研究上下文，不等同于事实关系。</p>
              </header>
              <div className={styles.relationGrid}>
                {relations.map((relation) => (
                  <article key={`${relation.kind}:${relation.entity.id}`}>
                    <div className={styles.relationTop}>
                      <span data-kind={relation.kind}>{relation.label}</span>
                      <em data-confidence={relation.confidence}>
                        {CONFIDENCE_LABELS[relation.confidence]}
                      </em>
                    </div>
                    <Link href={relation.href}>
                      <TypeIcon type={relation.entity.entityType} size={16} />
                      <strong>{relation.entity.name}</strong>
                    </Link>
                    {relation.sharedTracks.length ? (
                      <p>共同赛道：{relation.sharedTracks.join("、")}</p>
                    ) : null}
                    {relation.evidence.length ? (
                      <div className={styles.relationEvidence}>
                        {relation.evidence.map((evidence) => (
                          <a href={evidence.url} target="_blank" rel="noreferrer" key={evidence.url}>
                            <span>{evidence.eventDate || "日期未记录"} · {evidence.sourceName}</span>
                            <strong>{evidence.title}</strong>
                            <ExternalLink size={12} />
                          </a>
                        ))}
                      </div>
                    ) : (
                      <p className={styles.contextOnly}>暂无共同原文证据，仅因配置在同一追踪赛道而关联。</p>
                    )}
                  </article>
                ))}
              </div>
            </section>
          ) : null}
        </article>
      </div>
    </main>
  );
}
