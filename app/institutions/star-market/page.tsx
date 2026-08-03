import type { Metadata } from "next";
import { FileSearch } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { StarMarketInvestorDirectory } from "@/components/star-market-investor-directory";
import {
  starMarketInvestorGeneratedAt,
  starMarketInvestorMethodology,
  starMarketInvestorPrivacy,
  starMarketInvestorStats,
} from "@/lib/star-market-investor-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "科创板招股说明书机构股东抽取（测试版）",
  description:
    "从科创板上市公司公开招股说明书中自动抽取机构候选、持股字段、证据页码与机构级公开联系方式；当前结果仍需人工核验。",
};

export default function StarMarketInvestorPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04A / STAR MARKET INVESTORS · BETA</p>
        <h1>科创板招股说明书机构股东抽取（测试版）</h1>
        <p>
          从当前赛道内已追踪的科创板上市公司招股说明书中，自动抽取机构候选、持股字段、证据页码和机构级公开联系方式，并尝试连接站内投资机构目录。
        </p>
        <Link className="text-link" href="/institutions">
          返回投资机构目录 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="PROSPECTUS EXTRACTION CANDIDATES"
        title="自动抽取候选记录"
        description="按赛道和上市公司筛选；每条记录保留官方招股书原文与页码，名称和数值仍需人工核验。"
        count={starMarketInvestorStats.investors}
        countLabel="待核验抽取记录"
        icon={<FileSearch size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.warning} role="note" aria-label="测试版数据提示">
          <strong>测试版数据提示</strong>
          <p>
            本目录由 PDF 文本层自动抽取，当前尚未完成逐条人工审核。机构名称、持股比例和联系方式可能出现文本碎片、字段错配或关联错误；请以证据页及官方招股说明书为准，不应用于尽职调查、法律判断或投资决策。
          </p>
        </section>

        <section className={styles.methodology}>
          <div>
            <span>已覆盖上市公司</span>
            <strong>{starMarketInvestorStats.companies}</strong>
            <p>当前追踪配置中证券代码为 688xxx 的已启用 A 股公司，不代表完整科创板覆盖。</p>
          </div>
          <div>
            <span>匹配站内机构</span>
            <strong>{starMarketInvestorStats.linkedInstitutions}</strong>
            <p>自动抽取名称可与投资机构频道中的榜单机构或研究档案匹配。</p>
          </div>
          <div>
            <span>含联系字段记录</span>
            <strong>{starMarketInvestorStats.prospectusContacts}</strong>
            <p>统计自动关联到招股说明书机构级电话、邮箱、网址或办公地址的候选记录。</p>
          </div>
        </section>

        <section className={styles.notes}>
          <h2>数据口径</h2>
          <p>
            文件发现采用巨潮资讯结构化公告数据并保留官方 PDF 地址；PDF 使用文本层解析，不启用 OCR，也不绕过登录、验证码或访问控制。
          </p>
          <p>
            自然人股东不进入公开目录；手机号码、身份证件信息和家庭地址不会发布。机构联系方式仅在招股说明书中存在机构级公开字段时进入候选结果，但其归属仍需结合证据页核验。
          </p>
          <p>
            数据失败时保留上一版通过程序校验的快照。最近生成时间：
            {starMarketInvestorGeneratedAt
              ? new Date(starMarketInvestorGeneratedAt).toLocaleString("zh-CN", {
                  timeZone: "Asia/Taipei",
                  hour12: false,
                })
              : "等待首次生产采集"}
            。
          </p>
          <details>
            <summary>机器可读方法说明</summary>
            <pre>
              {JSON.stringify(
                {
                  methodology: starMarketInvestorMethodology,
                  privacy: starMarketInvestorPrivacy,
                },
                null,
                2,
              )}
            </pre>
          </details>
        </section>

        <StarMarketInvestorDirectory />
      </ChannelSplitLayout>
    </main>
  );
}
