import type { Metadata } from "next";
import { FileSearch } from "lucide-react";
import Link from "next/link";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { StarMarketInvestorDirectory } from "@/components/star-market-investor-directory";
import {
  starMarketInvestorGeneratedAt,
  starMarketInvestorMethodology,
  starMarketInvestorPrivacy,
  starMarketInvestorReviewManifestDecisionCount,
  starMarketInvestorStats,
} from "@/lib/star-market-investor-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "科创板招股说明书机构股东抽取（测试版）",
  description:
    "从科创板上市公司公开招股说明书中自动抽取机构候选；发布前质量门按同一证据行重建持股字段，人工决定写入版本化审核清单。",
};

export default function StarMarketInvestorPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04A / STAR MARKET INVESTORS · BETA</p>
        <h1>科创板招股说明书机构股东抽取（测试版）</h1>
        <p>
          从当前赛道内已追踪的科创板上市公司招股说明书中自动抽取机构候选。发布前质量门只接受候选名称之后同一证据行中的唯一持股数值；人工核验和人工排除决定由版本化审核清单记录。
        </p>
        <Link className="text-link" href="/institutions">
          返回投资机构目录 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="PROSPECTUS EXTRACTION REVIEW QUEUE"
        title="发布前质量门候选记录"
        description="按同一证据行重建持股字段并保留官方招股书证据页；人工决定包含审核键、审核人和时间。"
        count={starMarketInvestorStats.investors}
        countLabel="质量门后候选"
        icon={<FileSearch size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.warning} role="note" aria-label="测试版数据提示">
          <strong>测试版数据提示</strong>
          <p>
            质量门会删除跨行绑定的持股数值、隔离同一行存在多个比例的记录，并暂缓展示所有未核验候选的联系方式；但 PDF 文本层仍可能破坏原始表格结构。请以证据页及官方招股说明书为准，不应用于尽职调查、法律判断或投资决策。
          </p>
        </section>

        <section className={styles.methodology}>
          <div>
            <span>原始自动抽取</span>
            <strong>{starMarketInvestorStats.extracted}</strong>
            <p>保留在机器可读快照中，包含之后被发布前质量门隔离的审计记录。</p>
          </div>
          <div>
            <span>发布前质量门排除</span>
            <strong>{starMarketInvestorStats.rejected}</strong>
            <p>名称异常、证据不一致、多值歧义和疑似发行人自身记录不公开展示。</p>
          </div>
          <div>
            <span>待人工核验</span>
            <strong>{starMarketInvestorStats.needsReview}</strong>
            <p>其余候选默认待核验；程序不会自动授予“已人工核验”。</p>
          </div>
        </section>

        <section className={styles.notes}>
          <h2>数据口径</h2>
          <p>
            文件发现采用巨潮资讯结构化公告数据并保留官方 PDF 地址；PDF 使用文本层解析，不启用 OCR，也不绕过登录、验证码或访问控制。
          </p>
          <p>
            持股数和持股比例会在自动抽取完成后重新计算：仅使用候选机构名称之后、同一证据行中的唯一数值。候选名称之前的数值、其他行的数值以及同一行的多个比例均不会被猜测绑定。
          </p>
          <p>
            人工决定保存在 `config/star_market_investor_reviews.json`。每条决定以“公司 slug：候选 ID”为审核键，并要求填写 `status`、`reviewer` 和 ISO-8601 格式的 `reviewedAt`；清单中无法匹配当前候选的键会使发布任务失败，而不会静默丢失。
          </p>
          <p>
            审核状态分为 `verified`、`needs_review`、`rejected`。未完成人工核验的候选不展示机构联系方式；只有证据一致且由审核清单明确标记为 `verified` 的记录才允许公开联系字段。
          </p>
          <p>
            当前覆盖 {starMarketInvestorStats.companies} 家上市公司；质量门后候选 {starMarketInvestorStats.investors} 条，其中已人工核验 {starMarketInvestorStats.verified} 条；当前快照应用人工决定 {starMarketInvestorReviewManifestDecisionCount} 条，已核验联系字段 {starMarketInvestorStats.publicContacts} 条。
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
