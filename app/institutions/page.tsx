import type { Metadata } from "next";
import { InstitutionDirectory } from "@/components/institution-directory";
import {
  institutionDirectoryStats,
  institutionRankingSources,
} from "@/lib/institution-ranking-data";

export const metadata: Metadata = {
  title: "投资机构",
  description: "基于清科与投中专业榜单整理的中国股权投资机构目录，并连接现有中美机构研究档案。",
};

export default function InstitutionsPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / INVESTMENT INSTITUTIONS</p>
        <h1>投资机构</h1>
        <p>
          以清科 2025 年早期、VC、PE、国资、CVC 与并购主榜为机构名单基础，
          结合投中 2025 年度分类框架，并连接现有机构官网、代表性组合与近期公司事件。
        </p>
      </header>

      <div className="comparison-banner">
        <div><span>中国榜单机构</span><strong>{institutionDirectoryStats.china}</strong></div>
        <div><span>海外代表机构</span><strong>{institutionDirectoryStats.us}</strong></div>
        <p>
          共 {institutionDirectoryStats.total} 家机构、{institutionDirectoryStats.rankedRecords} 条清科榜单记录；
          {institutionDirectoryStats.detailedProfiles} 家已连接站内研究档案。
        </p>
      </div>

      <section className="comparison-columns" aria-label="专业榜单来源">
        {institutionRankingSources.map((source) => (
          <div key={source.publisher}>
            <span>{source.publisher} · {source.year}</span>
            <strong>{source.title}</strong>
            <p>{source.categories.join(" · ")}</p>
            <a className="source-link" href={source.url} target="_blank" rel="noreferrer">
              查看原始榜单
            </a>
          </div>
        ))}
      </section>

      <p className="data-note">
        榜单名次和入选状态按专业网站原始披露保存；卡片中的阶段和主题用于目录筛选，
        不替代机构官网对基金策略、管理规模或具体投资项目的正式披露。投中榜当前用于补充
        早期、VC、PE、中资/外资及产业榜单分类框架，不把未公开的单项名次推断到具体机构。
      </p>

      <InstitutionDirectory />
    </main>
  );
}
