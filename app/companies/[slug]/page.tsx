import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import { intelligenceEvents } from "@/lib/intelligence-data";

export function generateStaticParams(){return companies.map((item)=>({slug:item.slug}));}
export async function generateMetadata({params}:{params:Promise<{slug:string}>}):Promise<Metadata>{const {slug}=await params;const c=companies.find(i=>i.slug===slug);return{title:c?.name??"公司档案",description:c?.summary};}
export default async function CompanyDetail({params}:{params:Promise<{slug:string}>}) {
  const {slug}=await params; const company=companies.find(i=>i.slug===slug); if(!company)notFound();
  const events=intelligenceEvents.filter(i=>i.companySlug===slug);
  return <main className="page-shell subpage"><header className="entity-hero"><div><p className="eyebrow">{company.region} · {company.sector} · {company.status}</p><h1>{company.name}</h1><p>{company.englishName}</p><div className="hero-chips"><span>{company.stage}</span><span>置信度 {Math.round(company.confidence*100)}%</span><span>最近核验 2026-07-24</span></div></div><div className="entity-monogram">{company.name.slice(0,2).toUpperCase()}</div></header>
    <div className="detail-layout"><aside className="toc"><strong>公司档案</strong>{["基本信息","产品与业务","团队与缺口","融资与事件","竞争观察","十维分析","风险提示","来源"].map(i=><a href={`#${i}`} key={i}>{i}</a>)}</aside><article className="detail-article">
      <Section id="基本信息" title="基本信息"><dl className="facts-grid"><div><dt>成立时间</dt><dd>{company.founded??"未核验"}</dd></div><div><dt>总部</dt><dd>{company.headquarters??"未核验"}</dd></div><div><dt>当前阶段</dt><dd>{company.stage}</dd></div><div><dt>运营状态</dt><dd>{company.status}</dd></div></dl><p>{company.summary}</p></Section>
      <Section id="产品与业务" title="产品与业务"><p>{company.product}</p><div className="evidence-box"><strong>已确认事实</strong><p>产品定位来自公司官方页面；客户数量、收入、估值和市场份额未获得同等级公开材料时不展示。</p></div></Section>
      <Section id="团队与缺口" title="团队与信息缺口"><p className="data-note">首版只在公司官方简介或监管文件可交叉核实时收录核心团队履历。当前档案暂不展示未完成逐项核验的个人经历。</p></Section>
      <Section id="融资与事件" title="融资与重大事件"><div className="timeline">{events.length?events.map(e=><div key={e.id}><time>{e.publishedAt}</time><div><strong>{e.title}</strong><p>{e.summary}</p><a href={e.source.url} target="_blank" rel="noreferrer">{e.source.level} · {e.source.name}</a></div></div>):<p className="data-note">当前没有达到核验标准的融资记录。空状态不代表公司从未融资。</p>}</div></Section>
      <Section id="竞争观察" title="竞争观察"><p>以同赛道公司作为初步对照，不据此断言直接竞争关系。</p><div className="chip-list">{companies.filter(i=>i.sector===company.sector&&i.slug!==company.slug).slice(0,6).map(i=><Link href={`/companies/${i.slug}`} key={i.slug}>{i.name}</Link>)}</div></Section>
      <Section id="十维分析" title="项目分析"><div className="analysis-grid">{["项目愿景","用户痛点","行业市场","技术方案","竞争格局","商业模式","关键验证点","团队能力","发展趋势","融资与退出路径"].map((item,index)=><div key={item}><span>{String(index+1).padStart(2,"0")}</span><strong>{item}</strong><p>{index<4?"基于官方产品与公开材料持续核验。":"当前证据不足，暂不做精确评分。"}</p></div>)}</div></Section>
      <Section id="风险提示" title="风险提示"><ul className="risk-list">{["技术路线和规模化交付风险","商业化与客户集中度风险","竞争与替代路线风险","融资和现金流风险","监管与跨境合规风险","公开数据不完整风险"].map(i=><li key={i}>{i}</li>)}</ul></Section>
      <Section id="来源" title="原始来源"><a className="source-card" href={company.source.url} target="_blank" rel="noreferrer"><span>{company.source.level}</span><strong>{company.source.name}</strong><small>{company.source.url}</small></a></Section>
    </article><aside className="source-rail"><strong>相关机构</strong>{institutionCatalog.filter(i=>i.sectors.some(s=>company.sector.includes(s)||s.includes("科技"))).slice(0,4).map(i=><Link href={`/institutions/${i.slug}`} key={i.slug}>{i.name}<span>{i.stages}</span></Link>)}<strong>相关研究</strong>{reports.filter(r=>r.tags.some(t=>company.sector.includes(t)||t==="AI")).slice(0,3).map(r=><Link href={`/reports/${r.slug}`} key={r.slug}>{r.title}<span>{r.date}</span></Link>)}</aside></div>
  </main>
}
function Section({id,title,children}:{id:string;title:string;children:React.ReactNode}){return <section id={id} className="article-section"><p className="section-index">{id}</p><h2>{title}</h2>{children}</section>}
