import type { Metadata } from "next";
import { GlobalSearch } from "@/components/global-search";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { coreTechnologyEntities } from "@/lib/core-research-objects";
import { researchPeople } from "@/lib/people-data";
import type { SearchRecord } from "@/lib/search-index";
import { trackedSectors } from "@/lib/tracked-sectors";

export const metadata: Metadata = {
  title: "全局搜索",
  description: "搜索核心技术、核心赛道、核心人物、核心公司和辅助证据资料。",
};

const staticRecords: SearchRecord[] = [
  ...coreTechnologyEntities.map((item) => ({
    type: "技术" as const,
    title: item.name,
    text: `${item.summary} · ${item.trackNames.join(" / ")}`,
    href: `/tracking/entities/topic/${item.slug}`,
    region: "全球",
  })),
  ...trackedSectors.map((item) => ({
    type: "赛道" as const,
    title: item.name,
    text: `热度 ${item.heat} · 数据完整度 ${item.completeness}%`,
    href: `/technology/${item.slug}`,
    region: "全球",
  })),
  ...researchPeople.map((item) => ({
    type: "人物" as const,
    title: item.name,
    text: item.summary,
    href: `/people/${item.slug}`,
    region: "全球",
  })),
  ...companies.map((item) => ({
    type: "公司" as const,
    title: item.name,
    text: item.summary,
    href: `/companies/${item.slug}`,
    region: item.region,
  })),
  ...institutionCatalog.map((item) => ({
    type: "资料" as const,
    title: item.name,
    text: `投资机构 · ${item.stages} · ${item.sectors.join(" / ")}`,
    href: `/institutions/${item.slug}`,
    region: item.region,
  })),
  ...reports.map((item) => ({
    type: "资料" as const,
    title: item.title,
    text: `研究报告 · ${item.summary}`,
    href: `/reports/${item.slug}`,
    region: "全球",
  })),
];

export default function SearchPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">GLOBAL SEARCH</p>
        <h1>全局搜索</h1>
        <p>优先检索四类核心研究对象；事件索引在输入后按需加载，不再启动完整情报档案。</p>
      </header>
      <GlobalSearch staticRecords={staticRecords} />
    </main>
  );
}
