import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { companies, institutionCatalog } from "@/lib/catalog-data";
import { intelligenceEvents, snapshotDate } from "@/lib/intelligence-data";
import { getInstitutionProfile } from "@/lib/research-content";
import {
  getInstitutionVentureProfile,
  ventureProfileGeneratedAt,
  type VentureClassicCase,
  type VenturePortfolioCase,
  type VentureSource,
} from "@/lib/venture-profile-data";

export function generateStaticParams() {
  return institutionCatalog.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const institution = institutionCatalog.find((item) => item.slug === slug);
  const venture = getInstitutionVentureProfile(slug);
  return {
    title: institution?.name ?? "机构档案",
    description: venture?.overview,
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

  const staticProfile = getInstitutionProfile(institution);
  const venture = getInstitutionVentureProfile(slug);
  const aliases = [institution.name, institution.englishName]
    .filter(Boolean)
    .map((name) => name!.toLocaleLowerCase());
  const relatedEvents = intelligenceEvents
    .filter((event) => {
      const text = `${event.title} ${event.summary} ${(event.institutions ?? []).join(" ")}`.toLocaleLowerCase();
      return aliases.some((alias) => text.includes(alias));
    })
    .sort((a, b) => b.publishedAt.localeCompare(a.publishedAt))
    .slice(0, 12);
  const updateDate =
    venture?.updatedAt?.slice(0, 10) ||
    ventureProfileGeneratedAt?.slice(0, 10) ||
    snapshotDate;
  const overview = venture?.overview || staticProfile.thesis;
  const strategy =
    venture?.strategy ||
    `${institution.name}公开投资方向覆盖${institution.sectors.join("、")}，阶段以${institution.stages}为主。`;
  const team = venture?.team ?? [];
  const portfolio: VenturePortfolioCase[] = venture?.portfolio?.length
    ? venture.portfolio
    : staticProfile.portfolio.map((item) => ({
        name: item.name,
        companySlug: item.slug,
        summary: item.note,
      }));
  const recentInvestments = venture?.recentInvestments ?? [];
  const classicCases: VentureClassicCase[] = venture?.classicCases?.length
    ? venture.classicCases
    : deriveClassicCases(portfolio);
  const sources = uniqueSources([
    ...(venture?.sources ?? []),
    {
      name: institution.source.name,
      url: institution.source.url,
      level: institution.source.level,
      section: "机构官网",
    },
    ...relatedEvents.slice(0, 6).map((event) => ({
      name: event.source.name,
      url: event.source.url,
      level: event.source.level,
      section: event.type,
      title: event.title,
      publishedAt: event.publishedAt,
    })),
  ]);
  const sections = [
    "机构概览",
    "投资策略与阶段",
    "核心团队",
    "最近一年投资",
    "投资组合",
    "经典案例分析",
    "近期公开关联",
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
            <span>资料更新 {updateDate}</span>
            {venture && <span>证据完整度 {venture.evidenceScore ?? 0}%</span>}
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
          <Section id="机构概览" title="机构介绍">
            <p>{overview}</p>
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
                <dd>{updateDate}</dd>
              </div>
            </dl>
          </Section>

          <Section id="投资策略与阶段" title="投资策略、主题与阶段">
            <p>{strategy}</p>
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

          <Section id="核心团队" title="核心团队与合伙人">
            {team.length ? (
              <div className="entity-list">
                {team.map((member) => {
                  const content = (
                    <>
                      <strong>{member.name}</strong>
                      <span>
                        {[member.role, member.summary].filter(Boolean).join(" · ") ||
                          "公开团队成员"}
                      </span>
                    </>
                  );
                  return member.sourceUrl ? (
                    <a
                      href={member.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      key={`${member.name}-${member.role ?? ""}`}
                    >
                      {content}
                    </a>
                  ) : (
                    <div key={`${member.name}-${member.role ?? ""}`}>{content}</div>
                  );
                })}
              </div>
            ) : (
              <EvidenceEmpty>
                本轮未从机构官网团队页识别到可核对成员。系统将在后续刷新中继续提取合伙人、投资负责人及其公开职责。
              </EvidenceEmpty>
            )}
          </Section>

          <Section id="最近一年投资" title="最近一年投资项目汇总">
            <PortfolioList
              items={recentInvestments}
              emptyText="最近一年暂未从机构官网或公开投资动态中识别到带日期、项目和投资动作的完整记录。系统不会把无日期的组合页面误标为最近投资。"
            />
          </Section>

          <Section id="投资组合" title="投资案例与公开组合">
            <PortfolioList
              items={portfolio}
              emptyText="本轮尚未从机构官网识别到可核对的投资组合。页面保留官网入口并等待后续刷新。"
            />
          </Section>

          <Section id="经典案例分析" title="经典案例分析">
            {classicCases.length ? (
              <div className="analysis-grid">
                {classicCases.map((item, index) => {
                  const content = (
                    <>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <strong>{item.name}</strong>
                      <p>{item.analysis}</p>
                    </>
                  );
                  return item.companySlug ? (
                    <Link href={`/companies/${item.companySlug}`} key={item.name}>
                      {content}
                    </Link>
                  ) : item.sourceUrl ? (
                    <a
                      href={item.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      key={item.name}
                    >
                      {content}
                    </a>
                  ) : (
                    <div key={item.name}>{content}</div>
                  );
                })}
              </div>
            ) : (
              <EvidenceEmpty>
                当前组合证据不足以形成经典案例分析。系统将在识别到首次投资、后续轮次和上市或并购退出链条后自动生成。
              </EvidenceEmpty>
            )}
          </Section>

          <Section id="近期公开关联" title="近期公开关联">
            {relatedEvents.length ? (
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
            ) : (
              <EvidenceEmpty>
                当前资讯快照中未发现明确提及该机构的融资、产品、上市或退出事件。
              </EvidenceEmpty>
            )}
          </Section>

          <Section id="观察框架" title="后续观察">
            <div className="analysis-grid">
              {staticProfile.observation.map((item, index) => (
                <div key={item}>
                  <span>{String(index + 1).padStart(2, "0")}</span>
                  <strong>{item}</strong>
                  <p>通过机构公告、被投公司披露和监管文件交叉更新。</p>
                </div>
              ))}
            </div>
            {venture?.warnings?.length ? (
              <ul className="risk-list">
                {venture.warnings.slice(0, 4).map((warning) => (
                  <li key={warning}>资料限制：{warning}</li>
                ))}
              </ul>
            ) : null}
          </Section>

          <Section id="来源" title="机构原始资料与证据链">
            {sources.map((source) => (
              <a
                className="source-card"
                href={source.url}
                target="_blank"
                rel="noreferrer"
                key={source.url}
              >
                <span>
                  {source.publishedAt || source.section || source.level}
                </span>
                <strong>{source.title || source.name}</strong>
                <small>{source.url}</small>
              </a>
            ))}
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>证据完整度</span>
            <strong>{venture?.evidenceScore ?? 0}%</strong>
            <p>{venture ? "官网多页面抽取结果" : "等待首次档案刷新"}</p>
          </div>
          <div className="confidence-box">
            <span>核心团队</span>
            <strong>{team.length}</strong>
            <p>官网团队页与结构化数据</p>
          </div>
          <div className="confidence-box">
            <span>最近一年投资</span>
            <strong>{recentInvestments.length}</strong>
            <p>仅统计带日期的公开投资动作</p>
          </div>
          <div className="confidence-box">
            <span>公开组合样本</span>
            <strong>{portfolio.length}</strong>
            <p>来自机构官网与被投公司披露</p>
          </div>
          <div className="confidence-box">
            <span>经典案例</span>
            <strong>{classicCases.length}</strong>
            <p>投资逻辑、后续融资与退出链条</p>
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

function PortfolioList({
  items,
  emptyText,
}: {
  items: VenturePortfolioCase[];
  emptyText: string;
}) {
  if (!items.length) return <EvidenceEmpty>{emptyText}</EvidenceEmpty>;
  return (
    <div className="entity-list">
      {items.map((item, index) => {
        const content = (
          <>
            <strong>{item.name}</strong>
            <span>
              {[item.date, item.round, item.summary].filter(Boolean).join(" · ")}
            </span>
          </>
        );
        if (item.companySlug) {
          return (
            <Link
              href={`/companies/${item.companySlug}`}
              key={`${item.name}-${item.date ?? index}`}
            >
              {content}
            </Link>
          );
        }
        if (item.sourceUrl) {
          return (
            <a
              href={item.sourceUrl}
              target="_blank"
              rel="noreferrer"
              key={`${item.name}-${item.date ?? index}`}
            >
              {content}
            </a>
          );
        }
        return <div key={`${item.name}-${item.date ?? index}`}>{content}</div>;
      })}
    </div>
  );
}

function deriveClassicCases(portfolio: VenturePortfolioCase[]): VentureClassicCase[] {
  return portfolio.slice(0, 3).map((item) => {
    const company = item.companySlug
      ? companies.find((candidate) => candidate.slug === item.companySlug)
      : undefined;
    const analysis = company
      ? `${company.name}位于${company.sector}赛道，核心产品为${company.product}。该案例可用于观察机构在${company.stage}阶段的技术判断、后续资本支持与产业兑现；${company.status === "已上市" ? "公司已进入公开市场，可继续用上市后经营与市值表现检验投资逻辑。" : "公司仍处于非上市阶段，后续融资、规模化与退出路径是主要检验点。"}`
      : `${item.summary} 后续应继续核对首次投资、后续融资、经营兑现和退出路径。`;
    return {
      name: item.name,
      companySlug: item.companySlug,
      analysis,
      sourceUrl: item.sourceUrl,
    };
  });
}

function uniqueSources(sources: VentureSource[]) {
  const seen = new Set<string>();
  return sources.filter((source) => {
    if (!/^https?:\/\//u.test(source.url) || seen.has(source.url)) return false;
    seen.add(source.url);
    return true;
  });
}

function EvidenceEmpty({ children }: { children: React.ReactNode }) {
  return (
    <div className="source-card">
      <span>公开证据待补充</span>
      <strong>不使用未经核对的推测数据</strong>
      <small>{children}</small>
    </div>
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
