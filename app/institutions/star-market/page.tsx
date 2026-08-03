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
    "从科创板上市公司公开招股说明书中自动抽取机构候选；页面质量门排除明显错误，其余记录仍需人工核验。",
};

export default function StarMarketInvestorPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04A / STAR MARKET INVESTORS · BETA</p>
        <h1>科创板招股说明书机构股东抽取（测试版）</h1>
        <p>
          从当前赛道内已追踪的科创板上市公司招股说明书中自动抽取机构候选。页面质量门会排除明显的正文句子碎片、通用法律形式和疑似上市公司自身名称，其余记录默认等待人工核验。
        </p>
        <Link className="text-link" href="/institutions">
          返回投资机构目录 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="PROSPECTUS EXTRACTION REVIEW QUEUE"
        title="质量门后候选记录"
        description="排除明显错误并保留官方招股书证据页；可见候选不等同于已人工核验。"
        count={starMarketInvestorStats.investors}
        countLabel="质量门后候选"
        icon={<FileSearch size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.warning} role="note" aria-label="测试版数据提示">
          <strong>测试版数据提示</strong>
          <p>
            当前质量门在页面读取现有快照时运行，只能识别部分明显错误，不能修复解析器中的表格错位或联系方式归属问题。请以证据页及官方招股说明书为准，不应用于尽职调查、法律判断或投资决策。
          </p>
        </section>

        <section className={styles.methodology}>
          <div>
            <span>原始自动抽取</span>
            <strong>{starMarketInvestorStats.extracted}</strong>
            <p>来自现有招股说明书解析快照，包含之后被页面质量门排除的记录。</p>
          </div>
          <div>
            <span>页面质量门排除</span>
            <strong>{starMarketInvestorStats.rejected}</strong>
            <p>明显的句子碎片、通用法律形式及疑似发行人自身名称不再展示。</p>
          </div>
          <div>
            <span>待人工核验</span>
            <strong>{starMarketInvestorStats.needsReview}</strong>
            <p>其余自动抽取候选默认待核验；程序不会自动授予“已人工核验”。</p>
          </div>
        </section>

        <section className={styles.notes}>
          <h2>数据口径</h2>
          <p>
            文件发现采用巨潮资讯结构化公告数据并保留官方 PDF 地址；PDF 使用文本层解析，不启用 OCR，也不绕过登录、验证码或访问控制。
          </p>
          <p>
            本阶段先建立 `verified`、`needs_review`、`rejected` 三类审核状态，并对旧快照实施兼容性质量门。解析器仍需在下一阶段改为同一证据行绑定持股字段，并加强联系方式与机构主体的局部关联校验。
          </p>
          <p>
            当前覆盖 {starMarketInvestorStats.companies} 家上市公司；质量门后候选 {starMarketInvestorStats.investors} 条，其中已人工核验 {starMarketInvestorStats.verified} 条；匹配站内机构 {starMarketInvestorStats.linkedInstitutions} 条，含自动关联联系字段 {starMarketInvestorStats.prospectusContacts} 条。
          </p>
          <p>
            自然人股东不进入公开目录；手机号码、身份证件信息和家庭地址不会发布。数据失败时保留上一版通过程序校验的快照。最近生成时间：
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
