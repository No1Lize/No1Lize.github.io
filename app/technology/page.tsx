import type { Metadata } from "next";
import Link from "next/link";
import { SectorChart } from "@/components/sector-chart";
import { sectors } from "@/lib/intelligence-data";

export const metadata: Metadata = { title:"新兴科技", description:"十个新兴科技赛道的中美融资、事件与产业进展。" };

export default function TechnologyPage() {
  return <main className="page-shell subpage">
    <header className="page-header"><p className="eyebrow">02 / EMERGING TECHNOLOGY</p><h1>新兴科技</h1><p>热度衡量公开事件与资本活动，不代表投资价值。完整度不足时不推算缺失金额。</p></header>
    <section className="data-panel"><div className="section-heading"><div><p className="section-index">SIX-MONTH SAMPLE</p><h2>中美事件样本趋势</h2></div><span>来源：当前已核验公开资料快照</span></div><SectorChart /></section>
    <section className="sector-card-grid">{sectors.map((sector, index) => <Link href={`/technology/${sector.slug}`} className="sector-card" key={sector.slug}><div><span>{String(index+1).padStart(2,"0")}</span><strong>{sector.heat}</strong></div><h2>{sector.name}</h2><p>{sector.events} 项重大事件 · {sector.institutions} 家活跃机构</p><dl><div><dt>披露融资</dt><dd>{sector.fundingLabel}</dd></div><div><dt>完整度</dt><dd>{sector.completeness}%</dd></div></dl><i><b style={{width:`${sector.heat}%`}}/></i></Link>)}</section>
  </main>;
}
