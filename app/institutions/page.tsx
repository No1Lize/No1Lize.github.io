import type { Metadata } from "next";
import { Landmark } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { InstitutionDirectory } from "@/components/institution-directory";
import {
  institutionDirectoryStats,
  institutionRankingSources,
} from "@/lib/institution-ranking-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "投资机构",
  description: "基于清科与投中专业榜单整理的中国股权投资机构目录，并连接现有中美机构研究档案。",
};

export default function InstitutionsPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / INVESTMENT INSTITUTIONS</p>
        <h1>投资机构</h1>
        <p>
          以清科 2025 年早期、VC、PE、国资、CVC 与并购主榜为机构名单基础，
          结合投中年度榜单分类框架，并连接现有机构官网、研究档案与近期公司事件。
        </p>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="LATEST INSTITUTION PROFILES"
        title="真实机构档案"
        description="按地区与榜单类别筛选机构，查看投资阶段、主题标签、研究档案和可追溯来源。"
        count={institutionDirectoryStats.total}
        countLabel="公开机构快照"
        icon={<Landmark size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <div className={styles.summary}>
          <div>
            <span>中国榜单机构</span>
            <strong>{institutionDirectoryStats.china}</strong>
          </div>
          <div>
            <span>海外代表机构</span>
            <strong>{institutionDirectoryStats.us}</strong>
          </div>
          <p>
            共 {institutionDirectoryStats.rankedRecords} 条清科榜单记录；
            {institutionDirectoryStats.detailedProfiles} 家机构已连接站内研究档案。
          </p>
        </div>

        <p className={styles.methodNote}>
          榜单来源：{" "}
          {institutionRankingSources.map((source, index) => (
            <span key={source.url}>
              {index > 0 && "；"}
              <a href={source.url} target="_blank" rel="noreferrer">
                {source.publisher}《{source.title}》
              </a>
            </span>
          ))}
          。仅保留原始页面明确披露的名次；未排序榜单统一标记为“入选”，不推断具体位次。
        </p>

        <InstitutionDirectory compact pageSize={6} />
      </ChannelSplitLayout>
    </main>
  );
}
