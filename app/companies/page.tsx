import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { CompanyDirectory } from "@/components/company-directory";
import { CompanyProfileRefreshStatus } from "@/components/company-profile-refresh-status";
import { companies } from "@/lib/catalog-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "核心公司",
  description: "一级市场核心科技公司档案、产品、团队、融资与可追溯来源。",
};

export default function CompaniesPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">05 / CORE COMPANIES</p>
        <h1>核心公司</h1>
        <p>
          {companies.length} 家核心科技公司档案，连接核心技术、产业位置、团队、融资、公开动态、
          同赛道对照与原始来源。上市、并购和退出信息仅作为公司生命周期证据，不再独立成频道。
        </p>
      </header>

      <ChannelSplitLayout
        channel="companies"
        eyebrow="LATEST CORE COMPANY PROFILES"
        title="核心公司档案"
        description="按地区与赛道筛选公司，查看技术产品、发展阶段、融资过程、资料完整度及可追溯原始来源。"
        count={companies.length}
        countLabel="公开公司快照"
        icon={<Building2 size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <CompanyDirectory pageSize={6} />
        <CompanyProfileRefreshStatus />
      </ChannelSplitLayout>
    </main>
  );
}
