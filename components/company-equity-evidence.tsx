import { ExternalLink } from "lucide-react";
import {
  getCompanyProfessionalVentureProfile,
  type EquityChange,
  type EquityHolder,
  type ExternalInvestment,
} from "@/lib/professional-venture-data";

const statusLabels: Record<string, string> = {
  success: "已获取",
  no_data: "本轮无记录",
  disabled: "未启用",
  error: "调用失败",
};

function SourceLink({ url, label }: { url?: string; label?: string }) {
  if (!url) return label ? <span>{label}</span> : null;
  return (
    <a href={url} target="_blank" rel="noreferrer">
      {label || "查看来源"} <ExternalLink size={12} aria-hidden="true" />
    </a>
  );
}

function HolderList({ title, items }: { title: string; items: EquityHolder[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3>{title}</h3>
      <div className="entity-list">
        {items.map((holder) => {
          const detail = [
            holder.percent ? `持股 ${holder.percent}` : "",
            holder.subscribedCapital ? `认缴 ${holder.subscribedCapital}` : "",
            holder.paidCapital ? `实缴 ${holder.paidCapital}` : "",
            holder.relationship || "",
            ...holder.tags,
          ]
            .filter(Boolean)
            .join(" · ");
          const content = (
            <>
              <strong>{holder.name}</strong>
              <span>{detail || "数据库未披露持股比例或出资额"}</span>
              {holder.sourceName && <small>来源 · {holder.sourceName}</small>}
            </>
          );
          return holder.sourceUrl ? (
            <a
              href={holder.sourceUrl}
              target="_blank"
              rel="noreferrer"
              key={`${holder.name}-${holder.sourceUrl}`}
            >
              {content}
            </a>
          ) : (
            <div key={holder.name}>{content}</div>
          );
        })}
      </div>
    </div>
  );
}

function ChangeTimeline({ items }: { items: EquityChange[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3>股东与股权变更</h3>
      <div className="timeline">
        {items.map((change, index) => (
          <div key={`${change.date || "undated"}-${change.item}-${index}`}>
            <time>{change.date || "日期未披露"}</time>
            <div>
              <strong>{change.item}</strong>
              {(change.before || change.after) && (
                <p>
                  {change.before ? `变更前：${change.before}` : ""}
                  {change.before && change.after ? "；" : ""}
                  {change.after ? `变更后：${change.after}` : ""}
                </p>
              )}
              <SourceLink url={change.sourceUrl} label={change.sourceName || "查看数据库记录"} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function InvestmentList({ items }: { items: ExternalInvestment[] }) {
  if (!items.length) return null;
  return (
    <div>
      <h3>对外投资与持股</h3>
      <div className="entity-list">
        {items.map((investment) => {
          const detail = [
            investment.percent ? `持股 ${investment.percent}` : "",
            investment.amount ? `投资额 ${investment.amount}` : "",
            investment.registeredCapital
              ? `被投企业注册资本 ${investment.registeredCapital}`
              : "",
            investment.status || "",
          ]
            .filter(Boolean)
            .join(" · ");
          const content = (
            <>
              <strong>{investment.name}</strong>
              <span>{detail || "数据库未披露投资金额或持股比例"}</span>
              {investment.sourceName && <small>来源 · {investment.sourceName}</small>}
            </>
          );
          return investment.sourceUrl ? (
            <a
              href={investment.sourceUrl}
              target="_blank"
              rel="noreferrer"
              key={`${investment.name}-${investment.sourceUrl}`}
            >
              {content}
            </a>
          ) : (
            <div key={investment.name}>{content}</div>
          );
        })}
      </div>
    </div>
  );
}

export function CompanyEquityEvidence({ slug }: { slug: string }) {
  const professional = getCompanyProfessionalVentureProfile(slug);
  const equity = professional?.equityProfile;
  const sources = professional?.professionalSources ?? [];
  const hasCoreFacts = Boolean(
    equity &&
      (equity.legalName ||
        equity.creditCode ||
        equity.registeredCapital ||
        equity.shareholders.length ||
        equity.changes.length ||
        equity.externalInvestments.length),
  );

  return (
    <>
      {hasCoreFacts && equity ? (
        <>
          <dl className="facts-grid">
            <div>
              <dt>工商登记名称</dt>
              <dd>{equity.legalName || "未披露或尚未识别"}</dd>
            </div>
            <div>
              <dt>统一社会信用代码</dt>
              <dd>{equity.creditCode || "未披露或尚未识别"}</dd>
            </div>
            <div>
              <dt>登记状态</dt>
              <dd>{equity.registrationStatus || "未披露或尚未识别"}</dd>
            </div>
            <div>
              <dt>法定代表人</dt>
              <dd>{equity.legalRepresentative || "未披露或尚未识别"}</dd>
            </div>
            <div>
              <dt>注册资本</dt>
              <dd>{equity.registeredCapital || "未披露或尚未识别"}</dd>
            </div>
            <div>
              <dt>实缴资本</dt>
              <dd>{equity.paidUpCapital || "未披露或尚未识别"}</dd>
            </div>
          </dl>
          <p>
            核验状态：
            {equity.evidenceStatus === "cross-verified"
              ? "至少两个专业来源交叉一致"
              : equity.evidenceStatus === "single-source"
                ? "目前仅有一个专业来源"
                : "尚无可核对记录"}
            {equity.verifiedAt ? `；最近核验 ${equity.verifiedAt.slice(0, 10)}` : ""}。
          </p>
          <HolderList title="股东与出资信息" items={equity.shareholders} />
          <HolderList title="最终受益人与实际控制线索" items={equity.beneficialOwners} />
          <ChangeTimeline items={equity.changes} />
          <InvestmentList items={equity.externalInvestments} />
        </>
      ) : (
        <div className="source-card">
          <span>专业数据库待授权</span>
          <strong>尚未获取可核对的股东、持股比例或股权变更记录</strong>
          <small>
            系统不会抓取登录后页面或绕过验证码。企查查与天眼查仅在官方 API
            凭证已配置且付费调用明确启用时读取；鲸准仅发现可公开访问的投融资页面。
          </small>
        </div>
      )}

      <div>
        <h3>专业来源执行状态</h3>
        {sources.length ? (
          <div className="analysis-grid">
            {sources.map((source) => (
              <a href={source.url} target="_blank" rel="noreferrer" key={source.name}>
                <span>{statusLabels[source.status] || source.status}</span>
                <strong>{source.name}</strong>
                <p>{source.detail || "未返回执行说明。"}</p>
                <small>{source.records} 条结构化记录</small>
              </a>
            ))}
          </div>
        ) : (
          <div className="source-card">
            <span>尚未执行</span>
            <strong>专业融资与工商数据源尚未进入当前快照</strong>
            <small>下一次创业公司资料刷新会记录企查查、天眼查和鲸准各自的执行状态。</small>
          </div>
        )}
      </div>
    </>
  );
}
