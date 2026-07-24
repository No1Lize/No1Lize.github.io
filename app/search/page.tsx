import type { Metadata } from "next";
import { GlobalSearch } from "@/components/global-search";
export const metadata:Metadata={title:"全局搜索",description:"搜索公司、机构、赛道、人物、报告和事件。"};
export default function SearchPage(){return <main className="page-shell subpage"><header className="page-header"><p className="eyebrow">GLOBAL SEARCH</p><h1>全局搜索</h1><p>一次检索公司、机构、赛道、人物、报告以及定时任务收录的全部公开事件。</p></header><GlobalSearch /></main>}
