import type { Metadata } from "next";
import { GlobalSearch } from "@/components/global-search";
export const metadata:Metadata={title:"全局搜索",description:"搜索公司、机构、赛道、人物、报告和事件。"};
export default function SearchPage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">GLOBAL SEARCH</p><h1>全局搜索</h1><p>结果只来自已收录真实记录，不使用聊天式搜索或生成式补全。</p></header><GlobalSearch /></main>}
