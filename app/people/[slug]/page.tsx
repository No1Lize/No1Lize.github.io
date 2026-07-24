import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { people } from "@/lib/catalog-data";
import { getPersonProfile } from "@/lib/research-content";

const materialLabels: Record<string, string> = {
  authored_work: "本人著作",
  biography: "他人传记",
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
  return people.map((item) => ({ slug: item.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  return {
    title: people.find((item) => item.slug === slug)?.name ?? "人物研究",
  };
}

export default async function PersonDetail({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const person = people.find((item) => item.slug === slug);
  if (!person) notFound();
  const profile = getPersonProfile(person);

  return (
    <main className="page-shell subpage">
      <header className="entity-hero person-hero">
        <div>
          <p className="eyebrow">人物档案 · {person.englishName}</p>
          <h1>{person.name}</h1>
          <p>{person.role}</p>
          <div className="hero-chips">
            {profile.concepts.map((concept) => (
              <span key={concept.name}>{concept.name}</span>
            ))}
          </div>
        </div>
        <div className="person-monogram large">{person.name.slice(0, 1)}</div>
      </header>

      <div className="detail-layout">
        <aside className="toc">
          <strong>人物研究</strong>
          {["研究主线", "核心概念", "观点演进", "原始材料"].map((item) => (
            <a href={`#${item}`} key={item}>
              {item}
            </a>
          ))}
        </aside>

        <article className="detail-article">
          <Section id="研究主线" title="研究主线">
            <p>{profile.overview}</p>
          </Section>

          <Section id="核心概念" title="核心概念">
            <div className="concept-grid">
              {profile.concepts.map((concept, index) => {
                const evidence =
                  person.materials[
                    Math.min(concept.evidenceIndex, person.materials.length - 1)
                  ];
                return (
                  <div key={concept.name}>
                    <span>{String(index + 1).padStart(2, "0")}</span>
                    <strong>{concept.name}</strong>
                    <p>{concept.explanation}</p>
                    {evidence && (
                      <a href={evidence.url} target="_blank" rel="noreferrer">
                        相关材料 · {evidence.title}
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
          </Section>

          <Section id="观点演进" title="观点与方法演进">
            <div className="timeline">
              {profile.evolution.map((item, index) => (
                <div key={item}>
                  <time>{String(index + 1).padStart(2, "0")}</time>
                  <div>
                    <strong>{item}</strong>
                  </div>
                </div>
              ))}
            </div>
          </Section>

          <Section id="原始材料" title="公开材料">
            <div className="material-list">
              {person.materials.map((material) => (
                <a
                  href={material.url}
                  target="_blank"
                  rel="noreferrer"
                  key={`${material.title}-${material.date}`}
                >
                  <span>
                    {materialLabels[material.type] ?? material.type}
                  </span>
                  <div>
                    <strong>{material.title}</strong>
                    <p>{material.source}</p>
                  </div>
                  <time>{material.date}</time>
                </a>
              ))}
            </div>
          </Section>
        </article>

        <aside className="source-rail">
          <div className="confidence-box">
            <span>公开材料</span>
            <strong>{person.materials.length}</strong>
            <p>股东信、演讲、论文、文章与公开发文</p>
          </div>
          <div className="confidence-box">
            <span>研究概念</span>
            <strong>{profile.concepts.length}</strong>
            <p>每项关联原始材料</p>
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
