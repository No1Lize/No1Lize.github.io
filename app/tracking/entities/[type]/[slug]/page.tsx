import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  BookmarkPlus,
  Building2,
  Clock3,
  Cpu,
  ExternalLink,
  FileText,
  GitBranch,
  Star,
  UserRound,
} from "lucide-react";
import { TrackingEntityResearchEditor } from "@/components/tracking-entity-research-editor";
import {
  relatedTrackingResearchEntities,
  trackingResearchEntities,
  trackingResearchEntity,
  trackingResearchGeneratedAt,
  trackingResearchHref,
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
    title: entity ? `${entity.name} · 追踪研究` : "追踪对象研究",
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

  const related = relatedTrackingResearchEntities(entity, 8);
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
              <p className={styles.muted}>尚未记录结构化关注原因。下次从文章点击“＋追踪”时可补充。</p>
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

          {related.length ? (
            <section className={styles.related}>
              <header className={styles.sectionHeader}>
                <div>
                  <p className="section-index">RELATED ENTITIES</p>
                  <h2>共同赛道对象</h2>
                </div>
              </header>
              <div className={styles.relatedGrid}>
                {related.map((item) => (
                  <Link href={trackingResearchHref(item)} key={item.id}>
                    <span><TypeIcon type={item.entityType} size={15} />{TYPE_LABELS[item.entityType]}</span>
                    <strong>{item.name}</strong>
                    <small>{item.trackNames.join(" · ")}</small>
                  </Link>
                ))}
              </div>
            </section>
          ) : null}
        </article>
      </div>
    </main>
  );
}
