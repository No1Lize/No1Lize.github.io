import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ChannelSplitLayout } from "@/components/channel-split-layout";
import { CompanyCandidateDirectory } from "@/components/company-candidate-directory";
import { CompanyDirectory } from "@/components/company-directory";
import { CompanyProfileRefreshStatus } from "@/components/company-profile-refresh-status";
import { companies } from "@/lib/catalog-data";
import styles from "./page.module.css";

export const metadata: Metadata = {
  title: "创业案例",
  description: "中美科技创业公司档案、产品与来源。",
};

export default function CompaniesPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">03 / COMPANY CASES</p>
        <h1>创业案例</h1>
        <p>{companies.length} 家中美科技公司档案，连接产品定位、产业位置、公开动态、同赛道公司与原始来源。</p>
      </header>

      <ChannelSplitLayout
        channel="companies"
        eyebrow="LATEST COMPANY PROFILES"
        title="真实公司档案"
        description="按地区与赛道筛选公司，查看产品定位、发展阶段、资料完整度及可追溯原始来源。"
        count={companies.length}
        countLabel="公开公司快照"
        icon={<Building2 size={19} aria-hidden="true" />}
        bodyClassName={styles.body}
      >
        <CompanyDirectory pageSize={6} />
        <CompanyProfileRefreshStatus />
        <CompanyCandidateDirectory />
      </ChannelSplitLayout>
    </main>
  );
}
