import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { researchPeople, type PersonMaterial } from "@/lib/people-data";
import { getPersonProfile } from "@/lib/research-content";

const materialLabels: Record<string, string> = {
  official_profile: "官方档案",
  authored_work: "本人著作",
  biography: "人物背景",
  shareholder_letter: "股东信",
  interview: "采访",
  speech: "演讲",
  qa: "问答",
  article: "文章",
  public_post: "公开发文",
  public_document: "公开文件",
  compiled_work: "第三方整理",
  commentary: "第三方评论",
  research_paper: "研究论文",
};

export function generateStaticParams() {
  return researchPeople.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const person = researchPeople.find((item) => item.slug === slug);
  return {
    title: person?.name ?? "人物研究",
    description: person ? `${person.name}的背景、公司与机构、产品、作品、著作、演讲和公开材料。` : "人物研究",
  };
}

export default async function PersonDetail({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const person = researchPeople.find((item) => item.slug === slug);
  if (!person) notFound();
  const profile = getPersonProfile(person);
  const sections = [
    "人物背景",
    "公司与机构",
    "产品与项目",
    "作品与著作",
    "演讲与采访",
    "研究主线",
    "核心概念",
    "观点演进",
    "公开材料",
  ];

  return (
    <main className="page-shell subpage">
      <header className="entity-hero person-hero">
        <div>
          <p className="eyebrow">人物档案 · {person.englishName}</p>
          <h1>{person.name}</h1>
          <p>{person.role}</p>
          <div className="hero-chips">
            {person.sectors.map((sector) => <span key={sector}>{sector}</span>)}
            {person.handles.map((handle) => <span key={handle}>@{handle}</span>)}
            <span>{person.status === "complete" ? "资料较完整" : person.status === "partial" ? "持续补充" : "等待抓取"}</span>
          </div>
        </div>
        <div className="person-monogram large">{person.name.slice(0, 1)}</div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>人物研究</strong>
          {sections.map((item) => <a href={`#${item}`} key={item}>{item}</a>)}
        </aside>

        <article className="detail-article">
          <Section id="人物背景" title="人物背景">
            <p>{person.background || person.summary || "暂无可验证的背景资料，后台将在下一轮统一抓取时继续补充。"}</p>
            {person.aliases.length > 1 && <p className="method-note">别名：{person.aliases.join(" · ")}</p>}
          </Section>

          <Section id="公司与机构" title="公司与机构">
            <FactList values={person.organizations} empty="暂无已验证的公司、任职机构或研究机构信息。" />
          </Section>

          <Section id="产品与项目" title="产品与项目">
            <FactList values={person.products} empty="暂无已验证的产品或项目关联。" />
          </Section>

          <Section id="作品与著作" title="作品、论文与著作">
            <FactList values={[...person.works, ...person.books]} empty="暂无已验证的代表作品或著作条目；相关论文仍可在公开材料中查看。" />
          </Section>

          <Section id="演讲与采访" title="演讲、采访与公开对话">
            <MaterialList materials={person.speeches} empty="暂无已验证的演讲、采访或公开对话。" />
          </Section>

          <Section id="研究主线" title="研究主线">
            <p>{profile.overview || person.summary}</p>
          </Section>

          <Section id="核心概念" title="核心概念">
            {profile.concepts.length ? (
              <div className="concept-grid">
                {profile.concepts.map((concept, index) => {
                  const evidence = person.materials[Math.min(concept.evidenceIndex, person.materials.length - 1)];
                  return (
                    <div key={concept.name}>
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <strong>{concept.name}</strong>
                      <p>{concept.explanation}</p>
                      {evidence && <a href={evidence.url} target="_blank" rel="noreferrer">相关材料 · {evidence.title}</a>}
                    </div>
                  );
                })}
              </div>
            ) : <p>暂无足够材料提炼核心概念。</p>}
          </Section>

          <Section id="观点演进" title="观点与方法演进">
            {profile.evolution.length ? (
              <div className="timeline">
                {profile.evolution.map((item, index) => (
                  <div key={item}>
                    <time>{String(index + 1).padStart(2, "0")}</time>
                    <div><strong>{item}</strong></div>
                  </div>
                ))}
              </div>
            ) : <p>当前材料尚不足以形成可靠的时间演进判断。</p>}
          </Section>

          <Section id="公开材料" title="全部公开材料">
            <MaterialList materials={person.materials} empty="暂无可追溯公开材料。" />
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>公开材料</span>
            <strong>{person.materials.length}</strong>
            <p>Wikipedia、Wikidata、官方网站、论文、演讲与公开发文</p>
          </div>
          <div className="confidence-box">
            <span>所属赛道</span>
            <strong>{person.sectors.length || "—"}</strong>
            <p>{person.sectors.join("、") || "精选人物"}</p>
          </div>
          <div className="confidence-box">
            <span>最后更新</span>
            <strong>{person.updatedAt ? person.updatedAt.slice(0, 10) : "精选"}</strong>
            <p>后台使用统一人物资料管线持续更新</p>
          </div>
        </aside>
      </div>
    </main>
  );
}

function FactList({ values, empty }: { values: string[]; empty: string }) {
  if (!values.length) return <p>{empty}</p>;
  return <div className="concept-grid">{values.map((value, index) => <div key={value}><span>{String(index + 1).padStart(2, "0")}</span><strong>{value}</strong></div>)}</div>;
}

function MaterialList({ materials, empty }: { materials: PersonMaterial[]; empty: string }) {
  if (!materials.length) return <p>{empty}</p>;
  return (
    <div className="material-list">
      {materials.map((material) => (
        <a href={material.url} target="_blank" rel="noreferrer" key={`${material.title}-${material.date}-${material.url}`}>
          <span>{materialLabels[material.type] ?? material.type}</span>
          <div><strong>{material.title}</strong><p>{material.source}</p></div>
          <time>{material.date}</time>
        </a>
      ))}
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return <section id={id} className="article-section"><p className="section-index">{id}</p><h2>{title}</h2>{children}</section>;
}
