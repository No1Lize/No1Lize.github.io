import type { Metadata } from "next";
import { Cpu } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { trackedSectors } from "@/lib/tracked-sectors";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "新兴科技",
  description: "按用户配置动态追踪新兴科技赛道的中美融资、事件、公司与研究进展。",
};

export default function TechnologyPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">02 / EMERGING TECHNOLOGY</p>
        <h1>新兴科技</h1>
        <p>
          从当前启用的 {trackedSectors.length} 个赛道进入中美产业链、公司样本、投资机构、公开事件和关键研究变量。
          新增、停用或删除赛道后，页面会随配置重新构建。
        </p>
        <Link className="text-link" href="/tracking">
          管理赛道、关键词与信息源 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="technology"
        eyebrow="LATEST TECHNOLOGY TRACKS"
        title="真实赛道目录"
        description="按技术方向浏览产业结构、公司样本、关键变量、主要风险和最新公开事件。"
        count={trackedSectors.length}
        countLabel="公开赛道快照"
        icon={<Cpu size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className="sector-card-grid">
          {trackedSectors.map((sector, index) => (
            <Link
              href={`/technology/${sector.slug}`}
              className="sector-card"
              key={sector.slug}
            >
              <div>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{sector.heat}</strong>
              </div>
              <h2>{sector.name}</h2>
              <p>
                {sector.events} 项公开事件 · {sector.institutions} 家活跃机构 · {sector.associatedInstitutions} 家已关联
              </p>
              <dl>
                <div>
                  <dt>披露融资</dt>
                  <dd>{sector.fundingLabel}</dd>
                </div>
                <div>
                  <dt>完整度</dt>
                  <dd>{sector.completeness}%</dd>
                </div>
              </dl>
              <i>
                <b style={{ width: `${sector.heat}%` }} />
              </i>
            </Link>
          ))}
        </section>

        {!trackedSectors.length && (
          <section className={`empty-state ${styles.empty}`}>
            <strong>当前没有启用赛道</strong>
            <p>进入追踪配置页面，添加或重新启用至少一个赛道。</p>
            <Link className="text-link" href="/tracking">
              打开追踪配置 →
            </Link>
          </section>
        )}
      </ChannelSplitLayout>
    </main>
  );
}
