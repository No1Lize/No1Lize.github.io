import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft, Database, History, Network, Star } from "lucide-react";
import {
  TrackingEntityDirectory,
  type TrackingEntityDirectoryItem,
} from "@/components/tracking-entity-directory";
import {
  trackingResearchEntities,
  trackingResearchGeneratedAt,
  trackingResearchStats,
} from "@/lib/tracking-entity-research";
import styles from "./tracking-entities.module.css";

export const metadata: Metadata = {
  title: "追踪对象研究库",
  description: "汇总人工追踪的公司、人物与技术主题，并按可追溯公开材料生成研究时间线。",
};

const directoryItems: TrackingEntityDirectoryItem[] = trackingResearchEntities.map((entity) => ({
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
  attentionLevel: entity.attentionLevel,
  reasons: entity.reasons,
}));

const priorityCount = trackingResearchEntities.filter((entity) => entity.attentionLevel >= 4).length;

export default function TrackingEntitiesPage() {
  return (
    <main className="page-shell subpage">
      <header className={styles.hero}>
        <div>
          <Link href="/tracking" className={styles.back}>
            <ArrowLeft size={15} aria-hidden="true" />网站追踪管理
          </Link>
          <p className="eyebrow">TRACKED ENTITY RESEARCH</p>
          <h1>追踪对象研究库</h1>
          <p>
            将赛道配置、人工文章采集、公司候选和公开情报整合到同一研究入口。每个对象保留为什么开始关注、关注等级、首次来源和后续公开活动，不把普通关键词误当成正式公司档案。
          </p>
          <div className={styles.chips}>
            <span><Database size={14} />数据快照 {trackingResearchGeneratedAt.slice(0, 10) || "当前构建"}</span>
            <span><History size={14} />人工发现与公开事件统一排序</span>
            <span><Network size={14} />关系必须区分原文证据和共同赛道</span>
            <span><Star size={14} />重点观察 {priorityCount} 个</span>
          </div>
        </div>
        <dl className={styles.metrics}>
          <div><dt>追踪对象</dt><dd>{trackingResearchStats.entityCount}</dd></div>
          <div><dt>公司</dt><dd>{trackingResearchStats.companyCount}</dd></div>
          <div><dt>人物</dt><dd>{trackingResearchStats.personCount}</dd></div>
          <div><dt>技术／主题</dt><dd>{trackingResearchStats.topicCount}</dd></div>
          <div><dt>正式档案</dt><dd>{trackingResearchStats.formalCount}</dd></div>
          <div><dt>重点观察</dt><dd>{priorityCount}</dd></div>
        </dl>
      </header>

      <section className={styles.directory}>
        <div className={styles.sectionHeading}>
          <div>
            <p className="section-index">RESEARCH DIRECTORY</p>
            <h2>公司、人物和技术主题</h2>
          </div>
          <p>点击任一对象查看自动研究摘要、关注等级、原始发现文章、后续公开动态和证据关系。</p>
        </div>
        <TrackingEntityDirectory items={directoryItems} />
      </section>
    </main>
  );
}
