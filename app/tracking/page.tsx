import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Database, History, ShieldCheck } from "lucide-react";
import { publishedTrackingResearchStats } from "@/lib/published-tracking-entity-research";
import { trackingResearchGeneratedAt } from "@/lib/tracking-entity-research";

export const metadata: Metadata = {
  title: "公开追踪研究 | VCIQ",
  description: "基于当前 Git 提交构建的只读追踪研究快照。",
};

export default function TrackingPage() {
  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">PUBLIC TRACKING SNAPSHOT</p>
          <h1>公开追踪研究</h1>
          <p>
            此页面只展示当前 Git 提交中已经完成实体解析、并具有实质研究内容的公开对象。
            人工审核队列、候选消歧和写入操作不进入 Pages 静态工件。
          </p>
          <div className="hero-chips">
            <span><Database size={14} />构建快照 {trackingResearchGeneratedAt.slice(0, 10) || "当前提交"}</span>
            <span><ShieldCheck size={14} />仅发布已解析实体</span>
            <span><History size={14} />部署后内容固定</span>
          </div>
        </div>
        <dl className="facts-grid">
          <div><dt>公开对象</dt><dd>{publishedTrackingResearchStats.entityCount}</dd></div>
          <div><dt>公司</dt><dd>{publishedTrackingResearchStats.companyCount}</dd></div>
          <div><dt>人物</dt><dd>{publishedTrackingResearchStats.personCount}</dd></div>
          <div><dt>技术／主题</dt><dd>{publishedTrackingResearchStats.topicCount}</dd></div>
        </dl>
      </header>

      <section className="section-shell">
        <div className="section-heading">
          <div>
            <p className="section-index">RESEARCH DIRECTORY</p>
            <h2>查看公开研究对象</h2>
          </div>
          <p>目录和详情页均来自同一次构建，不在浏览器中读取或修改 GitHub 数据。</p>
        </div>
        <Link className="source-card" href="/tracking/entities">
          <span>只读目录</span>
          <strong>进入追踪对象研究库</strong>
          <small>公司、人物、技术主题与可追溯研究时间线</small>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>

      <section
        className="section-shell"
        id="company-candidate-review"
        aria-labelledby="private-review-boundary"
      >
        <span id="tracking-capture-inbox" />
        <div className="section-heading">
          <div>
            <p className="section-index">PRIVATE REVIEW BOUNDARY</p>
            <h2 id="private-review-boundary">审核与采集不在公开站点执行</h2>
          </div>
          <p>
            候选审核、实体消歧、文章采集和研究记录写入由仓库内受控流程完成；
            Pages 仅发布审核完成后的构建结果。
          </p>
        </div>
        <Link className="source-card" href="/tracking/entities">
          <span>公开结果</span>
          <strong>返回已发布研究目录</strong>
          <small>未解析或仍待人工判断的记录不会生成公开实体页面</small>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </main>
  );
}
