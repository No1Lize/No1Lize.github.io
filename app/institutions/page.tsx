import type { Metadata } from "next";
import { FileSearch, Landmark } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { InstitutionDirectory } from "@/components/institution-directory";
import {
  institutionDirectoryStats,
  institutionRankingSources,
} from "@/lib/institution-ranking-data";
import { starMarketInvestorStats } from "@/lib/star-market-investor-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "投资机构",
  description: "基于专业榜单、机构公开资料与科创板招股说明书整理的投资机构目录。",
};

export default function InstitutionsPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / INVESTMENT INSTITUTIONS</p>
        <h1>投资机构</h1>
        <p>
          以清科 2025 年早期、VC、PE、国资、CVC 与并购主榜为机构名单基础，
          结合投中年度榜单分类框架、机构官网、近期事件及科创板上市公司招股说明书中的机构股东关系。
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
        <Link className={styles.starEntry} href="/institutions/star-market">
          <div className={styles.starIcon}>
            <FileSearch size={20} aria-hidden="true" />
          </div>
          <div>
            <span>STAR MARKET PROSPECTUS DIRECTORY</span>
            <strong>科创板上市公司投资人</strong>
            <p>
              从公开招股说明书提取机构股东、发行前持股事实、证据页码和机构级公开联系方式。
            </p>
          </div>
          <dl>
            <div><dt>上市公司</dt><dd>{starMarketInvestorStats.companies}</dd></div>
            <div><dt>机构股东</dt><dd>{starMarketInvestorStats.investors}</dd></div>
            <div><dt>已关联机构</dt><dd>{starMarketInvestorStats.linkedInstitutions}</dd></div>
          </dl>
          <b>进入目录 →</b>
        </Link>

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
