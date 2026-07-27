import type { Metadata } from "next";
import { Building2 } from "lucide-react";
import { ChannelUpdateDirectory } from "@/components/channel-update-directory";
import { CompanyDirectory } from "@/components/company-directory";
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

      <div className={styles.splitLayout}>
        <div className={styles.updatesPanel}>
          <ChannelUpdateDirectory channel="companies" layout="split" />
        </div>

        <section className={styles.companyPanel} aria-labelledby="company-directory-title">
          <header className={styles.panelHeader}>
            <div>
              <p className="section-index">LATEST COMPANY PROFILES</p>
              <div className={styles.titleLine}>
                <Building2 size={19} aria-hidden="true" />
                <h2 id="company-directory-title">真实公司档案</h2>
              </div>
              <p className={styles.panelDescription}>
                按地区与赛道筛选公司，查看产品定位、发展阶段、资料完整度及可追溯原始来源。
              </p>
            </div>
            <div className={styles.snapshot}>
              <span>公开公司快照</span>
              <strong>{companies.length}</strong>
              <small>持续更新</small>
            </div>
          </header>
          <CompanyDirectory pageSize={6} />
        </section>
      </div>
    </main>
  );
}
