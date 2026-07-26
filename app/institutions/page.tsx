import type { Metadata } from "next";
import Link from "next/link";
import { ChannelUpdateDirectory } from "@/components/channel-update-directory";
import { institutionCatalog } from "@/lib/catalog-data";

export const metadata: Metadata = {
  title: "投资机构",
  description: "中美头部科技投资机构公开档案。",
};

export default function InstitutionsPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">04 / INVESTMENT INSTITUTIONS</p>
        <h1>投资机构</h1>
        <p>20 家中美科技投资机构，按市场、阶段与公开投资主题组织，并连接代表性组合与近期公司事件。</p>
      </header>

      <ChannelUpdateDirectory channel="institutions" />

      <div className="comparison-banner">
        <div><span>中国机构</span><strong>{institutionCatalog.filter((item) => item.region === "中国").length}</strong></div>
        <div><span>美国机构</span><strong>{institutionCatalog.filter((item) => item.region === "美国").length}</strong></div>
        <p>从机构策略进入公司与事件，观察资本在不同技术方向上的实际配置。</p>
      </div>

      <section className="catalog-grid institutions-grid">
        {institutionCatalog.map((institution) => (
          <Link href={`/institutions/${institution.slug}`} className="catalog-card" key={institution.slug}>
            <div className="catalog-top"><span>{institution.region}</span><span>{institution.type}</span></div>
            <div className="catalog-title">
              <i>{institution.name.slice(0, 2).toUpperCase()}</i>
              <div><h2>{institution.name}</h2><p>{institution.englishName}</p></div>
            </div>
            <dl>
              <div><dt>阶段</dt><dd>{institution.stages}</dd></div>
              <div><dt>重点赛道</dt><dd>{institution.sectors.join(" / ")}</dd></div>
            </dl>
            <span className="verified-source">官网 · {institution.source.name}</span>
          </Link>
        ))}
      </section>
    </main>
  );
}
