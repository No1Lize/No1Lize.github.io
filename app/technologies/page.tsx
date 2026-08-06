import type { Metadata } from "next";
import { Cpu } from "lucide-react";
import Link from "next/link";
import { coreTechnologyEntities } from "@/lib/core-research-objects";

export const metadata: Metadata = {
  title: "核心技术",
  description: "从公开证据和研究记录中整理具体技术、技术系统与关键能力。",
};

function evidenceScore(captureCount: number, articleCount: number, priority: number) {
  return Math.min(100, priority * 15 + captureCount * 12 + articleCount * 4);
}

export default function CoreTechnologiesPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">02 / CORE TECHNOLOGIES</p>
        <h1>核心技术</h1>
        <p>
          聚焦具体技术、技术系统与关键能力。宽泛产业方向归入“核心赛道”，
          这里只发布已有公开证据、人工发现或研究记录的技术对象。
        </p>
        <div className="hero-chips">
          <span><Cpu size={14} />{coreTechnologyEntities.length} 项公开技术</span>
          <span>按关注等级与证据强度排序</span>
          <span>详情保留可追溯时间线</span>
        </div>
      </header>

      <section className="section-shell">
        <div className="section-heading">
          <div>
            <p className="section-index">TECHNOLOGY DIRECTORY</p>
            <h2>技术研究对象</h2>
          </div>
          <p>技术与赛道分层管理，避免把产业领域、公司名称和技术名词混为同一实体。</p>
        </div>

        {coreTechnologyEntities.length ? (
          <div className="sector-card-grid">
            {coreTechnologyEntities.map((entity, index) => {
              const evidenceCount = entity.captureCount + entity.articleCount;
              const score = evidenceScore(
                entity.captureCount,
                entity.articleCount,
                entity.priority,
              );
              return (
                <Link
                  href={`/tracking/entities/topic/${entity.slug}`}
                  className="sector-card"
                  key={entity.id}
                >
                  <div>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{entity.priority ? `P${entity.priority}` : evidenceCount}</strong>
                  </div>
                  <h2>{entity.name}</h2>
                  <p>{entity.summary}</p>
                  <dl>
                    <div>
                      <dt>证据记录</dt>
                      <dd>{evidenceCount}</dd>
                    </div>
                    <div>
                      <dt>关联赛道</dt>
                      <dd>{entity.trackNames.length || "待归类"}</dd>
                    </div>
                  </dl>
                  <i aria-label={`研究证据强度 ${score}%`}>
                    <b style={{ width: `${score}%` }} />
                  </i>
                </Link>
              );
            })}
          </div>
        ) : (
          <div className="empty-state">
            <Cpu size={22} aria-hidden="true" />
            <strong>暂无达到公开门槛的具体技术对象</strong>
            <p>技术实体会在出现可追溯证据、人工发现或研究记录后自动进入目录。</p>
          </div>
        )}
      </section>
    </main>
  );
}
