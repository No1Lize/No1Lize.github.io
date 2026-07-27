import type { Metadata } from "next";
import { IpoWatchlist } from "@/components/ipo-watchlist";
import { listedCompaniesForDisplay } from "@/lib/listed-companies";

export const metadata: Metadata = {
  title: "上市跟踪",
  description: "A股、港股与美股科技企业公告和状态跟踪。",
};

export default function IpoPage() {
  return (
    <main className="page-shell subpage">
      <header className="page-header">
        <p className="eyebrow">05 / PUBLIC MARKETS</p>
        <h1>上市跟踪</h1>
        <p>
          跟踪 A 股、港股和美股科技公司的挂牌状态、经营指标、定期报告与重大事项披露。
          关注范围由齿轮后台统一管理。
        </p>
      </header>
      <IpoWatchlist companies={listedCompaniesForDisplay} />
    </main>
  );
}
