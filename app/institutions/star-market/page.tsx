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
  title: "科创板上市公司投资人",
  description:
    "从科创板上市公司公开招股说明书中整理机构股东、发行前持股事实、可追溯页码与机构级公开联系方式。",
};

export default function StarMarketInvestorPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04A / STAR MARKET INVESTORS</p>
        <h1>科创板上市公司投资人</h1>
        <p>
          从当前赛道内已追踪的科创板上市公司招股说明书中，提取发行前机构股东、持股事实、证据页码和机构级公开联系方式，并连接站内投资机构目录。
        </p>
        <Link className="text-link" href="/institutions">
          返回投资机构目录 →
        </Link>
      </header>

      <ChannelSplitLayout
        channel="institutions"
        eyebrow="PROSPECTUS SHAREHOLDER DIRECTORY"
        title="招股说明书机构股东目录"
        description="按赛道和上市公司筛选；每条记录保留官方招股书原文、页码与披露口径。"
        count={starMarketInvestorStats.investors}
        countLabel="公开机构股东记录"
        icon={<FileSearch size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <section className={styles.methodology}>
          <div>
            <span>上市公司</span>
            <strong>{starMarketInvestorStats.companies}</strong>
            <p>当前追踪配置中证券代码为 688xxx 的已启用 A 股公司。</p>
          </div>
          <div>
            <span>关联既有机构</span>
            <strong>{starMarketInvestorStats.linkedInstitutions}</strong>
            <p>名称可与投资机构频道中的榜单机构或研究档案统一匹配。</p>
          </div>
          <div>
            <span>机构联系渠道</span>
            <strong>{starMarketInvestorStats.prospectusContacts}</strong>
            <p>仅统计招股说明书直接披露的机构级电话、邮箱、网址或办公地址。</p>
          </div>
        </section>

        <section className={styles.notes}>
          <h2>数据口径</h2>
          <p>
            文件发现采用巨潮资讯结构化公告数据并保留官方 PDF 地址；PDF 使用文本层解析，不启用 OCR，也不绕过登录、验证码或访问控制。
          </p>
          <p>
            自然人股东不进入公开目录；手机号码、身份证件信息和家庭地址不会发布。机构联系方式必须在招股说明书中作为机构级信息明确披露，否则显示为“未披露”。
          </p>
          <p>
            数据失败时保留上一版已验证快照。最近生成时间：
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
