import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Database, History, Network } from "lucide-react";
import {
  TrackingEntityDirectory,
  type TrackingEntityDirectoryItem,
} from "@/components/tracking-entity-directory";
import {
  publishedTrackingResearchEntities,
  publishedTrackingResearchStats,
} from "@/lib/published-tracking-entity-research";
import { trackingResearchGeneratedAt } from "@/lib/tracking-entity-research";
import styles from "./tracking-entities.module.css";

export const metadata: Metadata = {
  title: "追踪证据图谱",
  description: "汇总核心公司、核心人物与具体技术，并按可追溯公开材料生成研究时间线。",
};

const directoryItems: TrackingEntityDirectoryItem[] = publishedTrackingResearchEntities.map((entity) => ({
  id: entity.id,
  entityType: entity.entityType,
  slug: entity.slug,
  name: entity.name,
  aliases: entity.aliases,
  trackNames: entity.trackNames,
  state: entity.state,
  formalLabel: entity.formalLabel,
  candidateStatus: entity.candidateStatus,
  summary: entity.summary,
  firstTrackedAt: entity.firstTrackedAt,
  lastActivityAt: entity.lastActivityAt,
  captureCount: entity.captureCount,
  articleCount: entity.articleCount,
  reasons: entity.reasons,
  priority: entity.priority,
  priorityLabel: entity.priorityLabel,
  priorityStars: entity.priorityStars,
}));

export default function TrackingEntitiesPage() {
  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div>
          <Link href="/tracking" className={styles.back}>
            <ArrowLeft size={15} aria-hidden="true" />公开追踪研究
          </Link>
          <p className="eyebrow">RESEARCH EVIDENCE GRAPH</p>
          <h1>追踪证据图谱</h1>
          <p>
            将核心赛道配置、人工发现和公开情报整合到同一证据层。公司、人物和技术对象保留
            关注原因、首次来源与后续活动；机构、报告和市场披露只作为关系或证据，不另立研究对象。
          </p>
          <div className={styles.chips}>
            <span><Database size={14} />数据快照 {trackingResearchGeneratedAt.slice(0, 10) || "当前构建"}</span>
            <span><History size={14} />人工发现与公开事件统一排序</span>
            <span><Network size={14} />按共同赛道关联研究对象</span>
          </div>
        </div>
        <dl className={styles.metrics}>
          <div><dt>证据对象</dt><dd>{publishedTrackingResearchStats.entityCount}</dd></div>
          <div><dt>公司</dt><dd>{publishedTrackingResearchStats.companyCount}</dd></div>
          <div><dt>人物</dt><dd>{publishedTrackingResearchStats.personCount}</dd></div>
          <div><dt>技术</dt><dd>{publishedTrackingResearchStats.topicCount}</dd></div>
          <div><dt>正式档案</dt><dd>{publishedTrackingResearchStats.formalCount}</dd></div>
          <div><dt>人工采集</dt><dd>{publishedTrackingResearchStats.capturedCount}</dd></div>
          <div><dt>重点研究</dt><dd>{publishedTrackingResearchStats.priorityCount}</dd></div>
        </dl>
      </header>

      <section className={styles.directory}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">EVIDENCE DIRECTORY</p>
            <h2>公司、人物和具体技术</h2>
          </div>
          <p>点击任一对象查看研究原因、原始发现文章、后续公开动态和相关对象。</p>
        </div>
        <TrackingEntityDirectory items={directoryItems} />
      </section>
    </main>
  );
}
