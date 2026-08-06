import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  BookmarkPlus,
  Building2,
  CircleHelp,
  Clock3,
  Cpu,
  ExternalLink,
  FileText,
  GitBranch,
  Link2,
  Network,
  ShieldCheck,
  Sparkles,
  Star,
  TrendingUp,
  UserRound,
} from "lucide-react";
import { TrackingEntityResearchEditor } from "@/components/tracking-entity-research-editor";
import {
  trackingResearchBrief,
  trackingResearchRelations,
} from "@/lib/tracking-entity-insights";
import {
  publishedTrackingResearchEntities,
  publishedTrackingResearchEntity,
} from "@/lib/published-tracking-entity-research";
import {
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
  high: "直接证据",
  medium: "共同原文",
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

export function generateStaticParams() {
  return publishedTrackingResearchEntities.map((entity) => ({
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
  const entity = isEntityType(type) ? publishedTrackingResearchEntity(type, slug) : undefined;
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
  const entity = publishedTrackingResearchEntity(type, slug);
  if (!entity) notFound();

  const brief = trackingResearchBrief(entity);
  const relations = trackingResearchRelations(entity, 12);
  const evidenceRelations = relations.filter((relation) => relation.evidenceCount > 0);
  const contextualRelations = relations.filter((relation) => relation.evidenceCount === 0);
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
            {entity.priority ? <span>{entity.priorityStars} · {entity.priorityLabel}</span> : null}
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
        <div><span><Star size={16} />关注等级</span><strong>{entity.priority || "未设置"}</strong></div>
      </section>

      <div className={styles.layout}>
        <aside className={styles.sidebar}>
          <section>
            <p className="section-index">WHY TRACKED</p>
            <h2>为什么关注</h2>
            {entity.reasons.length ? (
              <div className={styles.reasonList}>
                {entity.reasons.map((reason) => <span key={reason}>{reason}</span>)}
              </div>
            ) : (
              <p className={styles.muted}>尚未记录结构化关注原因。可在下方“研究维护”中补充。</p>
            )}
            {entity.researchThesis ? (
              <div className={styles.notes}>
                <strong>当前研究判断</strong>
                <p>{entity.researchThesis}</p>
              </div>
            ) : null}
            {entity.notes.length ? (
              <div className={styles.notes}>
                {entity.notes.map((note) => <p key={note}>{note}</p>)}
              </div>
            ) : null}
          </section>

          <TrackingEntityResearchEditor
            entityId={entity.id}
            entityType={entity.entityType}
            entityName={entity.name}
            initialRecord={entity.researchRecord}
          />

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
          <section className={styles.brief}>
            <header className={styles.sectionHeader}>
              <div>
                <p className="section-index">EVIDENCE-BACKED BRIEF</p>
                <h2>自动研究摘要</h2>
              </div>
              <span className={styles.briefPriority}>
                {entity.priorityStars || "☆☆☆☆☆"} · {brief.priorityLabel}
              </span>
            </header>
            <div className={styles.briefLead}>
              <span><Sparkles size={17} aria-hidden="true" />规则汇总</span>
              <h3>{brief.headline}</h3>
              <p>{brief.summary}</p>
            </div>
            {brief.signals.length ? (
              <div className={styles.signalGrid}>
                {brief.signals.map((signal) => (
                  <div key={signal.category}>
                    <span><TrendingUp size={14} aria-hidden="true" />{signal.label}</span>
                    <strong>{signal.count}</strong>
                    <small>{displayDate(signal.latestAt)} · {signal.latestTitle}</small>
                  </div>
                ))}
              </div>
            ) : null}
            <div className={styles.briefColumns}>
              <section>
                <h3><ShieldCheck size={16} aria-hidden="true" />重点观察</h3>
                {brief.watchItems.length ? (
                  <ul>{brief.watchItems.map((item) => <li key={item}>{item}</li>)}</ul>
                ) : (
                  <p>尚未形成结构化观察项。</p>
                )}
              </section>
              <section>
                <h3><CircleHelp size={16} aria-hidden="true" />待核问题</h3>
                {brief.openQuestions.length ? (
                  <ul>{brief.openQuestions.map((item) => <li key={item}>{item}</li>)}</ul>
                ) : (
                  <p>当前没有规则识别出的待核问题。</p>
                )}
              </section>
            </div>
            <p className={styles.methodology}>{brief.methodology}</p>
          </section>

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
                  <span>{
                    item.origin === "manual-capture"
                      ? "人工发现"
                      : item.origin === "analyst-note"
                        ? "研究笔记"
                        : "公开动态"
                  }</span>
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
                    {item.url ? (
                      <a href={item.url} target="_blank" rel="noreferrer">
                        查看原文<ExternalLink size={13} aria-hidden="true" />
                      </a>
                    ) : null}
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
            <section className={styles.relationships}>
              <header className={styles.sectionHeader}>
                <div>
                  <p className="section-index">RELATIONS & CONTEXT</p>
                  <h2>关系与共同赛道</h2>
                </div>
                <p>竞争、合作、人物和共同出现必须绑定共同原文；共同赛道只表示研究上下文。</p>
              </header>

              {evidenceRelations.length ? (
                <div className={styles.relationGrid}>
                  {evidenceRelations.map((relation) => (
                    <article className={styles.relationCard} data-confidence={relation.confidence} key={relation.entity.id}>
                      <header>
                        <div>
                          <span><TypeIcon type={relation.entity.entityType} size={14} />{TYPE_LABELS[relation.entity.entityType]}</span>
                          <em>{relation.label} · {CONFIDENCE_LABELS[relation.confidence]}</em>
                        </div>
                        <Link href={relation.href}>
                          {relation.entity.name}<ExternalLink size={13} aria-hidden="true" />
                        </Link>
                      </header>
                      {relation.sharedTracks.length ? <p>共同赛道：{relation.sharedTracks.join("、")}</p> : null}
                      <div className={styles.relationEvidence}>
                        {relation.evidence.map((evidence) => (
                          <a href={evidence.url} target="_blank" rel="noreferrer" key={`${relation.entity.id}-${evidence.url}`}>
                            <span>{displayDate(evidence.eventDate)} · {evidence.sourceName} · {evidence.eventType}</span>
                            <strong>{evidence.title}</strong>
                            <Link2 size={13} aria-hidden="true" />
                          </a>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              ) : null}

              {contextualRelations.length ? (
                <div className={styles.contextualRelations}>
                  <h3><Network size={16} aria-hidden="true" />赛道上下文</h3>
                  <div>
                    {contextualRelations.map((relation) => (
                      <Link href={relation.href} key={relation.entity.id}>
                        <span><TypeIcon type={relation.entity.entityType} size={14} />{relation.label}</span>
                        <strong>{relation.entity.name}</strong>
                        <small>{relation.sharedTracks.join(" · ")}</small>
                      </Link>
                    ))}
                  </div>
                </div>
              ) : null}
            </section>
          ) : null}
        </article>
      </div>
    </main>
  );
}