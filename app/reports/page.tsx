import type { Metadata } from "next";
import Link from "next/link";
import { reports } from "@/lib/catalog-data";

export const metadata: Metadata={title:"研究报告",description:"赛道、公司、IPO、机构和人物研究。"};
export default function ReportsPage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">06 / RESEARCH</p><h1>研究报告</h1><p>围绕 AI、机器人、芯片、商业航天和自动驾驶，连接核心判断、公司样本、事实时间线与后续跟踪指标。</p></header><div className="report-list">{reports.map((r,index)=><Link href={`/reports/${r.slug}`} key={r.slug}><span>{String(index+1).padStart(2,"0")}</span><div><p>{r.type} · {r.date}</p><h2>{r.title}</h2><strong>{r.summary}</strong><div>{r.tags.map(t=><i key={t}>{t}</i>)}</div></div><small>{r.sources} 个来源</small></Link>)}</div></main>}
