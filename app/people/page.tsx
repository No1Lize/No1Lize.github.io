import type { Metadata } from "next";
import Link from "next/link";
import { people } from "@/lib/catalog-data";

export const metadata: Metadata={title:"人物研究",description:"重要投资人物的原始材料、概念与观点演化。"};
export default function PeoplePage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">07 / PEOPLE</p><h1>人物研究</h1><p>本人材料、传记、第三方整理和评论明确分型；摘要不会伪装成原话。</p></header><div className="people-grid">{people.map(p=><Link href={`/people/${p.slug}`} key={p.slug}><div className="person-monogram">{p.name.slice(0,1)}</div><p>{p.englishName}</p><h2>{p.name}</h2><span>{p.role}</span><strong>{p.summary}</strong><div>{p.concepts.map(c=><i key={c}>{c}</i>)}</div><small>{p.materials.length} 条可追溯材料</small></Link>)}</div></main>}
