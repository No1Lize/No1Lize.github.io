import type { Metadata } from "next";
import Link from "next/link";
import { SectorChart } from "@/components/sector-chart";
import { sectors } from "@/lib/intelligence-data";

export const metadata: Metadata = { title:"新兴科技", description:"十个新兴科技赛道的中美融资、事件与产业进展。" };

export default function TechnologyPage() {
  return <main className="page-shell subpage">
    <header className="page-header"><p className="eyebrow">02 / EMERGING TECHNOLOGY</p><h1>新兴科技</h1><p>从十大赛道进入中美产业链、公司样本、投资机构、公开事件和关键研究变量。</p></header>
    <section className="data-panel"><div className="section-heading"><div><p className="section-index">SIX-MONTH ACTIVITY</p><h2>中美事件趋势</h2></div><span>公司公告与监管文件 · 自动更新</span></div><SectorChart /></section>
    <section className="sector-card-grid">{sectors.map((sector, index) => <Link href={`/technology/${sector.slug}`} className="sector-card" key={sector.slug}><div><span>{String(index+1).padStart(2,"0")}</span><strong>{sector.heat}</strong></div><h2>{sector.name}</h2><p>{sector.events} 项重大事件 · {sector.institutions} 家活跃机构</p><dl><div><dt>披露融资</dt><dd>{sector.fundingLabel}</dd></div><div><dt>完整度</dt><dd>{sector.completeness}%</dd></div></dl><i><b style={{width:`${sector.heat}%`}}/></i></Link>)}</section>
  </main>;
}
