import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { heatMethodology, intelligenceEvents, sectors } from "@/lib/intelligence-data";

export function generateStaticParams() { return sectors.map((sector) => ({slug:sector.slug})); }
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata> {
  const {slug}=await params; const sector=sectors.find((item)=>item.slug===slug); return {title:sector?.name ?? "赛道"};
}
export default async function SectorDetail({params}:{params:Promise<{slug:string}>}) {
  const {slug}=await params; const sector=sectors.find((item)=>item.slug===slug); if(!sector) notFound();
  const relatedCompanies=companies.filter((item)=>item.sector===sector.name).slice(0,8);
  const events=intelligenceEvents.filter((item)=>item.sector===sector.name);
  return <main className="page-shell subpage">
    <header className="entity-hero"><div><p className="eyebrow">SECTOR DOSSIER · 数据完整度 {sector.completeness}%</p><h1>{sector.name}</h1><p>本页按产业结构、公司、机构和可追溯事件组织，不使用关系网络或缺少来源的推算。</p></div><div className="hero-stat"><span>HeatScore</span><strong>{sector.heat}</strong><small>关注与资本活动</small></div></header>
    <div className="detail-layout"><aside className="toc"><strong>本页目录</strong>{["赛道定义","中美对照","产业链","代表公司","活跃机构","最新事件","方法与风险"].map((item)=><a href={`#${item}`} key={item}>{item}</a>)}</aside>
      <article className="detail-article">
        <Section id="赛道定义" title="赛道定义"><p>{sector.name}档案汇集相关公司的产品定位、公开资本事件和上市状态。当前版本以已核验公司官网、监管文件和机构披露为主。</p></Section>
        <Section id="中美对照" title="中美发展对照"><div className="comparison-columns"><div><span>中国</span><strong>{relatedCompanies.filter(i=>i.region==="中国").length} 家样本公司</strong><p>重点观察供应链、工程化与应用落地。</p></div><div><span>美国</span><strong>{relatedCompanies.filter(i=>i.region==="美国").length} 家样本公司</strong><p>重点观察基础研究、平台生态与资本开支。</p></div></div></Section>
        <Section id="产业链" title="产业链结构"><div className="chain"><Link href="/companies">上游 · 核心技术与部件</Link><Link href="/companies">中游 · 平台与系统</Link><Link href="/companies">下游 · 产品与行业应用</Link></div><p className="data-note">仅展示当前可核验层级；节点不会因视觉完整性而补造公司。</p></Section>
        <Section id="代表公司" title="代表公司"><div className="entity-list">{relatedCompanies.length?relatedCompanies.map((item)=><Link href={`/companies/${item.slug}`} key={item.slug}><strong>{item.name}</strong><span>{item.region} · {item.product}</span></Link>):<p className="data-note">当前快照尚无满足信源要求的公司记录。</p>}</div></Section>
        <Section id="活跃机构" title="活跃投资机构"><div className="chip-list">{institutionCatalog.filter(i=>i.sectors.some(s=>sector.name.includes(s)||s.includes("科技"))).slice(0,7).map(i=><Link href={`/institutions/${i.slug}`} key={i.slug}>{i.name}</Link>)}</div></Section>
        <Section id="最新事件" title="最新事件"><div className="timeline">{events.length?events.map(item=><div key={item.id}><time>{item.publishedAt}</time><div><strong>{item.title}</strong><p>{item.summary}</p><a href={item.source.url} target="_blank" rel="noreferrer">{item.source.level} · {item.source.name}</a></div></div>):<p className="data-note">暂无通过当前核验门槛的事件，保留空状态。</p>}</div></Section>
        <Section id="方法与风险" title="方法、风险与反证"><p>{heatMethodology}</p><p>热度不衡量公司质量或未来回报。样本对公开披露更积极的公司存在偏差；跨市场披露制度不同，事件数量不能直接解释为产业绝对强弱。</p></Section>
      </article>
      <aside className="source-rail"><strong>相关研究</strong>{reports.filter(r=>r.tags.some(tag=>sector.name.includes(tag)||tag==="AI")).slice(0,3).map(r=><Link href={`/reports/${r.slug}`} key={r.slug}>{r.title}<span>{r.date}</span></Link>)}<div className="confidence-box"><span>数据完整度</span><strong>{sector.completeness}%</strong><p>最后更新 2026-07-24</p></div></aside>
    </div>
  </main>;
}
function Section({id,title,children}:{id:string;title:string;children:React.ReactNode}){return <section id={id} className="article-section"><p className="section-index">{id.toUpperCase()}</p><h2>{title}</h2>{children}</section>}
