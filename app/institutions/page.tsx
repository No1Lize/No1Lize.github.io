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
  description: "基于公开榜单、机构官网与可追溯公开材料整理的投资机构目录。",
};

export default function InstitutionsPage() {
  const qingkeSource = institutionRankingSources[0];
  const chinaventureSource = institutionRankingSources[1];

  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / INVESTMENT INSTITUTIONS</p>
        <h1>投资机构</h1>
        <p>
          机构名单与名次主要以清科 2025 年早期、VC、PE、国资、CVC 与并购主榜为基础；
          投中年度榜单目前用于分类参考，并结合机构官网、近期公开事件及测试版招股说明书抽取结果。
        </p>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="LATEST INSTITUTION PROFILES"
        title="公开资料机构档案"
        description="按地区与榜单类别筛选机构，查看投资阶段、主题标签、研究档案和可追溯来源。"
        count={institutionDirectoryStats.total}
        countLabel="收录机构 · 2025 榜单"
        icon={<Landmark size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <Link className={styles.starEntry} href="/institutions/star-market">
          <div className={styles.starIcon}>
            <FileSearch size={20} aria-hidden="true" />
          </div>
          <div>
            <span>BETA / STAR MARKET PROSPECTUS EXTRACTION</span>
            <strong>科创板招股说明书机构股东抽取（测试版）</strong>
            <p>
              从公开招股说明书自动抽取机构候选、持股字段和证据页码。当前未完成逐条人工审核，请以原招股说明书为准。
            </p>
          </div>
          <dl>
            <div><dt>已覆盖公司</dt><dd>{starMarketInvestorStats.companies}</dd></div>
            <div><dt>自动抽取记录</dt><dd>{starMarketInvestorStats.investors}</dd></div>
            <div><dt>匹配站内机构</dt><dd>{starMarketInvestorStats.linkedInstitutions}</dd></div>
          </dl>
          <b>查看测试目录 →</b>
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
          名单与名次主要来源：{" "}
          <a href={qingkeSource.url} target="_blank" rel="noreferrer">
            {qingkeSource.publisher}《{qingkeSource.title}》
          </a>
          ；分类参考：{" "}
          <a href={chinaventureSource.url} target="_blank" rel="noreferrer">
            {chinaventureSource.publisher}《{chinaventureSource.title}》
          </a>
          。当前结构化排名记录仅保存清科榜单明确披露的名次；未排序榜单统一标记为“入选”，不推断具体位次。
        </p>

        <InstitutionDirectory compact pageSize={6} />
      </ChannelSplitLayout>
    </main>
  );
}
