import type { Metadata } from "next";
import { Network } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { trackedSectors } from "@/lib/tracked-sectors";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心赛道",
  description: "按一级市场研究配置追踪核心赛道的公司、人物、技术、融资与产业变化。",
};

export default function TechnologyPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">03 / CORE TRACKS</p>
        <h1>核心赛道</h1>
        <p>
          从当前启用的 {trackedSectors.length} 个核心赛道进入产业结构、关键技术、核心公司、
          关键人物、资本事件和持续验证变量。具体技术对象独立收录在“核心技术”目录。
        </p>
        <Link className="text-link" href="/tracking">
          查看公开追踪研究与发布规则 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="technology"
        eyebrow="LATEST CORE TRACKS"
        title="核心赛道目录"
        description="按产业方向浏览结构、样本公司、关键变量、主要风险和最新公开事件。"
        count={trackedSectors.length}
        countLabel="公开赛道快照"
        icon={<Network size={19} aria-hidden="true" />}
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
            <strong>当前没有启用核心赛道</strong>
            <p>赛道配置由仓库内受控流程维护，并在下一次构建中发布。</p>
            <Link className="text-link" href="/tracking">
              查看公开追踪研究 →
            </Link>
          </section>
        )}
      </ChannelSplitLayout>
    </main>
  );
}
