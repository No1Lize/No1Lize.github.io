import type { Metadata } from "next";
import Link from "next/link";
import { ipoCompanies } from "@/lib/catalog-data";

export const metadata: Metadata={title:"上市跟踪",description:"A股、港股与美股科技企业公告和状态跟踪。"};
export default function IpoPage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">05 / PUBLIC MARKETS</p><h1>上市跟踪</h1><p>按市场实际流程和监管来源分别记录，不把 A 股、港股与美股状态强行映射为同一体系。</p></header><div className="market-tabs">{(["A股","港股","美股"] as const).map(m=><div key={m}><span>{m}</span><strong>{ipoCompanies.filter(i=>i.market===m).length}</strong><small>跟踪公司</small></div>)}</div><div className="table-wrap"><table className="data-table"><thead><tr><th>企业</th><th>市场 / 代码</th><th>赛道</th><th>当前状态</th><th>最近跟踪</th><th>来源</th></tr></thead><tbody>{ipoCompanies.map(i=><tr key={i.slug}><td><Link href={`/ipo/${i.slug}`}>{i.name}</Link></td><td>{i.market} · {i.ticker}</td><td>{i.sector}</td><td><span className="status-label">{i.status}</span></td><td>{i.latest}</td><td><a href={i.source.url} target="_blank" rel="noreferrer">{i.source.name}</a></td></tr>)}</tbody></table></div></main>}
