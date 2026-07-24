import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog, reports } from "@/lib/catalog-data";
import {
  eventsForTrackedSector,
  getTrackedSector,
  trackedSectors,
} from "@/lib/tracked-sectors";
import { heatMethodology, snapshotDate } from "@/lib/intelligence-data";
import { reportContent } from "@/lib/research-content";

const institutionKeywords: Record<string, string[]> = {
  "AI / AGI": ["AI", "企业科技", "企业软件", "TMT", "科技"],
  机器人: ["先进制造", "制造", "硬科技", "科技", "工业", "国防科技"],
  半导体: ["硬科技", "先进制造", "制造", "科技"],
  新能源: ["气候科技", "先进制造", "制造", "科技"],
  生物科技: ["生物科技", "医疗"],
};

export function generateStaticParams() {
  return trackedSectors.map((sector) => ({ slug: sector.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  return { title: sector?.name ?? "赛道" };
}

export default async function SectorDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const sector = getTrackedSector(slug);
  if (!sector) notFound();

  const relatedCompanies = companies
    .filter((item) => item.sector === sector.name)
    .slice(0, 12);
  const keywords = [
    ...(institutionKeywords[sector.name] ?? []),
    ...sector.tracking.keywords,
  ];
  const relatedInstitutions = institutionCatalog
    .filter((institution) =>
      institution.sectors.some((focus) =>
        keywords.some(
          (keyword) => focus.includes(keyword) || keyword.includes(focus),
        ),
      ),
    )
    .slice(0, 10);
  const events = eventsForTrackedSector(sector)
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const relatedReports = reports.filter((report) =>
    reportContent[report.slug]?.eventSectors.includes(sector.name),
  );

  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">SECTOR DOSSIER · {sector.events} 项公开事件</p>
          <h1>{sector.name}</h1>
          <p>{sector.definition}</p>
          <div className="hero-chips">
            {sector.subsectors.map((item) => <span key={item}>{item}</span>)}
          </div>
        </div>
        <div className="hero-stat">
          <span>HeatScore</span>
          <strong>{sector.heat}</strong>
          <small>{sector.sourceCount} 个来源</small>
        </div>
      </header>

      <div className="detail-layout">
        <article className="detail-article">
          <Section id="赛道定义" title="赛道定义"><p>{sector.definition}</p></Section>
          <Section id="中美对照" title="中美发展对照">
            <div className="comparison-columns">
              <div><span>中国</span><strong>{relatedCompanies.filter((item) => item.region === "中国").length} 家样本公司</strong><p>{sector.chinaLens}</p></div>
              <div><span>美国</span><strong>{relatedCompanies.filter((item) => item.region === "美国").length} 家样本公司</strong><p>{sector.usLens}</p></div>
            </div>
          </Section>
          <Section id="产业链" title="产业链结构">
            <div className="chain">{sector.chain.map((node) => <Link href="/companies" key={node.title}><strong>{node.title}</strong><span>{node.detail}</span></Link>)}</div>
          </Section>
          <Section id="代表公司" title="代表公司">
            <div className="entity-list">{relatedCompanies.map((company) => <Link href={`/companies/${company.slug}`} key={company.slug}><strong>{company.name}</strong><span>{company.region} · {company.product}</span></Link>)}</div>
          </Section>
          <Section id="研究重点" title="关键研究变量">
            <div className="analysis-grid">{sector.researchFocus.map((item,index)=><div key={item}><span>{String(index+1).padStart(2,"0")}</span><strong>{item}</strong></div>)}</div>
          </Section>
          <Section id="风险" title="主要风险"><ul className="risk-list">{sector.risks.map((risk)=><li key={risk}>{risk}</li>)}</ul></Section>
          <Section id="数据口径" title="热度计算口径"><p>{heatMethodology}</p><p>更新：{snapshotDate}</p></Section>
        </article>
        <aside className="source-rail">
          <strong>相关研究</strong>
          {relatedReports.map((report)=><Link href={`/reports/${report.slug}`} key={report.slug}>{report.title}<span>{report.date}</span></Link>)}
        </aside>
      </div>
    </main>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return <section id={id} className="article-section"><p className="section-index">{id}</p><h2>{title}</h2>{children}</section>;
}
