import type { Metadata } from "next";
import { CompanyDirectory } from "@/components/company-directory";

export const metadata: Metadata = { title:"创业案例", description:"中美科技创业公司档案、产品与来源。" };
export default function CompaniesPage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">03 / COMPANY CASES</p><h1>创业案例</h1><p>首版收录 50 家中美科技公司；金额、估值或团队经历缺少可靠来源时不展示。</p></header><CompanyDirectory /></main>}
