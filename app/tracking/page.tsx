import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, Database, History, ShieldCheck } from "lucide-react";
import { coreResearchObjectStats } from "@/lib/core-research-objects";
import { trackingResearchGeneratedAt } from "@/lib/tracking-entity-research";

export const metadata: Metadata = {
  title: "公开追踪研究 | VCIQ",
  description: "支撑核心技术、核心赛道、核心人物和核心公司的只读研究快照。",
};

const objectDirectories = [
  {
    label: "核心技术",
    href: "/technologies",
    description: "具体技术、技术系统与关键能力",
  },
  {
    label: "核心赛道",
    href: "/technology",
    description: "产业结构、关键变量和长期验证框架",
  },
  {
    label: "核心人物",
    href: "/people",
    description: "创始人、科学家、工程负责人和关键决策者",
  },
  {
    label: "核心公司",
    href: "/companies",
    description: "一级市场科技公司、融资过程和生命周期证据",
  },
] as const;

export default function TrackingPage() {
  return (
    <main className="page-shell subpage">
      <header className="entity-hero">
        <div>
          <p className="eyebrow">PUBLIC RESEARCH OBJECT SNAPSHOT</p>
          <h1>公开追踪研究</h1>
          <p>
            追踪系统只服务于核心技术、核心赛道、核心人物和核心公司四类对象。
            机构、报告、监管披露和上市信息作为证据或关系层，不再独立定义研究主线。
          </p>
          <div className="hero-chips">
            <span><Database size={14} />构建快照 {trackingResearchGeneratedAt.slice(0, 10) || "当前提交"}</span>
            <span><ShieldCheck size={14} />仅发布已解析实体</span>
            <span><History size={14} />部署后内容固定</span>
          </div>
        </div>
        <dl className="facts-grid">
          <div><dt>核心技术</dt><dd>{coreResearchObjectStats.technologyCount}</dd></div>
          <div><dt>核心赛道</dt><dd>{coreResearchObjectStats.trackCount}</dd></div>
          <div><dt>核心人物</dt><dd>{coreResearchObjectStats.personCount}</dd></div>
          <div><dt>核心公司</dt><dd>{coreResearchObjectStats.companyCount}</dd></div>
        </dl>
      </header>

      <section className="section-shell">
        <div className="section-heading">
          <div>
            <p className="section-index">FOUR RESEARCH OBJECTS</p>
            <h2>进入四类公开研究目录</h2>
          </div>
          <p>各目录来自同一次 Git 构建；辅助证据不会被误建成新的一级频道。</p>
        </div>
        {objectDirectories.map((directory) => (
          <Link className="source-card" href={directory.href} key={directory.href}>
            <span>公开对象</span>
            <strong>{directory.label}</strong>
            <small>{directory.description}</small>
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        ))}
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
          <span>证据图谱</span>
          <strong>查看已发布追踪实体</strong>
          <small>未解析或仍待人工判断的记录不会生成公开实体页面</small>
          <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </section>
    </main>
  );
}
