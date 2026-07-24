import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { institutionCatalog } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { getInstitutionProfile } from "@/lib/research-content";

export function generateStaticParams() {
  return institutionCatalog.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  return {
    title:
      institutionCatalog.find((item) => item.slug === slug)?.name ?? "机构档案",
  };
}

export default async function InstitutionDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const institution = institutionCatalog.find((item) => item.slug === slug);
  if (!institution) notFound();

  const profile = getInstitutionProfile(institution);
  const aliases = [institution.name, institution.englishName]
    .filter(Boolean)
    .map((name) => name!.toLocaleLowerCase());
  const relatedEvents = intelligenceEvents
    .filter((event) => {
      const text = `${event.title} ${event.summary} ${(event.institutions ?? []).join(" ")}`.toLocaleLowerCase();
      return aliases.some((alias) => text.includes(alias));
    })
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 10);
  const sections = [
    "机构概览",
    "策略与阶段",
    ...(profile.portfolio.length ? ["代表性公开组合"] : []),
    ...(relatedEvents.length ? ["近期公开关联"] : []),
    "观察框架",
    "来源",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">
            {institution.region} · {institution.type}
          </p>
          <h1>{institution.name}</h1>
          <p>{institution.englishName}</p>
          <div className="hero-chips">
            <span>{institution.stages}</span>
            {institution.sectors.map((sector) => (
              <span key={sector}>{sector}</span>
            ))}
          </div>
        </div>
        <div className="entity-monogram">
          {institution.name.slice(0, 2).toUpperCase()}
        </div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>机构档案</strong>
          {sections.map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="机构概览" title="机构概览">
            <p>{profile.thesis}</p>
            <dl className="facts-grid">
              <div>
                <dt>机构类型</dt>
                <dd>{institution.type}</dd>
              </div>
              <div>
                <dt>主要阶段</dt>
                <dd>{institution.stages}</dd>
              </div>
              <div>
                <dt>主要市场</dt>
                <dd>{institution.region}</dd>
              </div>
              <div>
                <dt>资料更新</dt>
                <dd>{snapshotDate}</dd>
              </div>
            </dl>
          </Section>

          <Section id="策略与阶段" title="投资主题与阶段">
            <div className="insight-grid">
              {institution.sectors.map((sector) => (
                <div key={sector}>
                  <span>重点主题</span>
                  <strong>{sector}</strong>
                  <p>结合新增项目、后续轮融资和退出事件持续观察。</p>
                </div>
              ))}
              <div>
                <span>阶段覆盖</span>
                <strong>{institution.stages}</strong>
                <p>用于判断项目进入组合时的成熟度与后续资本需求。</p>
              </div>
            </div>
          </Section>

          {profile.portfolio.length > 0 && (
            <Section id="代表性公开组合" title="代表性公开组合">
              <div className="entity-list">
                {profile.portfolio.map((item) =>
                  item.slug ? (
                    <Link href={`/companies/${item.slug}`} key={item.name}>
                      <strong>{item.name}</strong>
                      <span>{item.note}</span>
                    </Link>
                  ) : (
                    <div key={item.name}>
                      <strong>{item.name}</strong>
                      <span>{item.note}</span>
                    </div>
                  ),
                )}
              </div>
            </Section>
          )}

          {relatedEvents.length > 0 && (
            <Section id="近期公开关联" title="近期公开关联">
              <div className="timeline">
                {relatedEvents.map((event) => (
                  <div key={event.id}>
                    <time>{event.publishedAt}</time>
                    <div>
                      <strong>{event.title}</strong>
                      <p>{event.summary}</p>
                      <a
                        href={event.source.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {event.source.name}
                      </a>
                    </div>
                  </div>
                ))}
              </div>
            </Section>
          )}

          <Section id="观察框架" title="后续观察">
            <div className="analysis-grid">
              {profile.observation.map((item, index) => (
                <div key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item}</strong>
                  <p>通过机构公告、被投公司披露和监管文件交叉更新。</p>
                </div>
              ))}
            </div>
          </Section>

          <Section id="来源" title="机构原始资料">
            <a
              className="source-card"
              href={institution.source.url}
              target="_blank"
              rel="noreferrer"
            >
              <span>{institution.source.level}</span>
              <strong>{institution.source.name}</strong>
              <small>{institution.source.url}</small>
            </a>
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>公开组合样本</span>
            <strong>{profile.portfolio.length}</strong>
            <p>来自机构官网与被投公司披露</p>
          </div>
          <div className="confidence-box">
            <span>关联动态</span>
            <strong>{relatedEvents.length}</strong>
            <p>融资、产品与退出事件</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function Section({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} className="article-section">
      <p className="section-index">{id}</p>
      <h2>{title}</h2>
      {children}
    </section>
  );
}
