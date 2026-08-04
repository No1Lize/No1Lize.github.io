"use client";

import {
  ArrowUpRight,
  Building2,
  FileText,
  Mail,
  MapPin,
  Phone,
  Search,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import {
  starInvestorInstitutionHref,
  starInvestorReviewLabels,
  starInvestorReviewReasonLabels,
  starMarketInvestorCompanies,
  starMarketInvestorRecords,
  starMarketInvestorStats,
  type StarInvestorReviewStatus,
} from "@/lib/star-market-investor-data";
import styles from "./star-market-investor-directory.module.css";

function numberLabel(value?: number): string {
  if (value === undefined || !Number.isFinite(value)) return "未可靠提取";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿股`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万股`;
  return `${value.toLocaleString("zh-CN")} 股`;
}

function reviewTimeLabel(value?: string): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("zh-CN", {
    timeZone: "Asia/Taipei",
    hour12: false,
  });
}

type ReviewFilter = "all" | Exclude<StarInvestorReviewStatus, "rejected">;

export function StarMarketInvestorDirectory() {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("全部赛道");
  const [company, setCompany] = useState("全部公司");
  const [reviewFilter, setReviewFilter] = useState<ReviewFilter>("all");
  const [contactOnly, setContactOnly] = useState(false);

  const sectors = useMemo(
    () => ["全部赛道", ...new Set(starMarketInvestorCompanies.map((item) => item.sector))],
    [],
  );
  const companies = useMemo(
    () => ["全部公司", ...starMarketInvestorCompanies.map((item) => item.name)],
    [],
  );

  const filtered = useMemo(() => {
    const needle = query.normalize("NFKC").trim().toLocaleLowerCase("zh-CN");
    return starMarketInvestorRecords.filter((record) => {
      if (sector !== "全部赛道" && record.company.sector !== sector) return false;
      if (company !== "全部公司" && record.company.name !== company) return false;
      if (reviewFilter !== "all" && record.investor.reviewStatus !== reviewFilter) return false;
      if (contactOnly && record.investor.contactStatus !== "prospectus-public") return false;
      if (!needle) return true;
      const institution = record.directoryInstitution;
      return [
        record.investor.name,
        record.investor.investorType,
        record.investor.reviewKey,
        record.investor.reviewedBy,
        record.company.name,
        record.company.ticker,
        record.company.sector,
        institution?.name,
        institution?.fullName,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(needle));
    });
  }, [company, contactOnly, query, reviewFilter, sector]);

  return (
    <div className={styles.directory}>
      <section className={styles.stats} aria-label="科创板招股说明书自动抽取审核统计">
        <div><span>原始抽取</span><strong>{starMarketInvestorStats.extracted}</strong></div>
        <div><span>质量门后候选</span><strong>{starMarketInvestorStats.investors}</strong></div>
        <div><span>待人工核验</span><strong>{starMarketInvestorStats.needsReview}</strong></div>
        <div><span>已人工核验</span><strong>{starMarketInvestorStats.verified}</strong></div>
        <div><span>自动排除</span><strong>{starMarketInvestorStats.rejected}</strong></div>
      </section>

      <div className={styles.filters}>
        <label className={styles.search}>
          <Search size={15} aria-hidden="true" />
          <input
            aria-label="搜索自动抽取机构候选"
            placeholder="搜索候选名称、审核键、公司、代码或赛道"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <select aria-label="按赛道筛选" value={sector} onChange={(event) => setSector(event.target.value)}>
          {sectors.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select aria-label="按上市公司筛选" value={company} onChange={(event) => setCompany(event.target.value)}>
          {companies.map((item) => <option key={item}>{item}</option>)}
        </select>
        <select
          aria-label="按审核状态筛选"
          value={reviewFilter}
          onChange={(event) => setReviewFilter(event.target.value as ReviewFilter)}
        >
          <option value="all">全部可见候选</option>
          <option value="verified">已人工核验</option>
          <option value="needs_review">待人工核验</option>
        </select>
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={contactOnly}
            onChange={(event) => setContactOnly(event.target.checked)}
          />
          仅显示已核验联系字段
        </label>
        <span className={styles.count}>显示 {filtered.length} 条候选</span>
      </div>

      {filtered.length ? (
        <section className={styles.grid} aria-label="科创板招股说明书质量门后候选记录">
          {filtered.map((record) => {
            const { investor, company: listedCompany, directoryInstitution } = record;
            const contact = investor.publicContact;
            const prospectusPage = `${listedCompany.prospectus.url}#page=${investor.sourcePage}`;
            const reasonLabels = investor.reviewReasons
              .map((reason) => starInvestorReviewReasonLabels[reason] ?? reason)
              .filter((reason, index, values) => values.indexOf(reason) === index);
            const reviewKey = investor.reviewKey ?? `${listedCompany.slug}:${investor.id}`;
            return (
              <article className={styles.card} key={`${listedCompany.slug}:${investor.id}`}>
                <div className={styles.cardTop}>
                  <span>{investor.investorType}</span>
                  <span>{listedCompany.sector}</span>
                  <span className={styles.reviewBadge} data-review-status={investor.reviewStatus}>
                    {starInvestorReviewLabels[investor.reviewStatus]}
                  </span>
                </div>

                <div className={styles.titleRow}>
                  <div className={styles.icon}><Building2 size={18} /></div>
                  <div>
                    <h2>{investor.name}</h2>
                    <p>
                      抽取自 {listedCompany.name}（{listedCompany.ticker}）招股说明书
                    </p>
                  </div>
                </div>

                <dl className={styles.holdings}>
                  <div>
                    <dt>同一证据行持股数</dt>
                    <dd>{numberLabel(investor.preIpoShares)}</dd>
                  </div>
                  <div>
                    <dt>同一证据行比例</dt>
                    <dd>
                      {investor.preIpoOwnershipPct === undefined
                        ? "未可靠提取"
                        : `${investor.preIpoOwnershipPct.toFixed(4)}%`}
                    </dd>
                  </div>
                  <div>
                    <dt>证据页</dt>
                    <dd>第 {investor.sourcePage} 页</dd>
                  </div>
                </dl>

                <p className={styles.evidence}>证据摘录：{investor.evidence}</p>
                <p className={styles.reviewNote}>审核键：{reviewKey}</p>
                {reasonLabels.length > 0 && (
                  <p className={styles.reviewNote}>审核提示：{reasonLabels.join("；")}</p>
                )}
                {investor.reviewStatus === "verified" && investor.reviewedBy && (
                  <p className={styles.reviewNote}>
                    人工核验：{investor.reviewedBy}
                    {investor.reviewedAt ? ` · ${reviewTimeLabel(investor.reviewedAt)}` : ""}
                    {investor.reviewNote ? ` · ${investor.reviewNote}` : ""}
                  </p>
                )}

                <div className={styles.contact}>
                  {contact?.officeAddress && (
                    <p><MapPin size={13} />{contact.officeAddress}</p>
                  )}
                  {contact?.phone && (
                    <a href={`tel:${contact.phone}`}><Phone size={13} />{contact.phone}</a>
                  )}
                  {contact?.email && (
                    <a href={`mailto:${contact.email}`}><Mail size={13} />{contact.email}</a>
                  )}
                  {contact?.website && (
                    <a href={contact.website} target="_blank" rel="noreferrer">
                      <ArrowUpRight size={13} />已核验招股书网站字段
                    </a>
                  )}
                  {!contact && investor.contactStatus === "withheld-pending-review" && (
                    <p className={styles.muted}>联系字段暂缓展示，待机构候选完成逐条人工核验。</p>
                  )}
                  {!contact && investor.contactStatus === "not-disclosed-in-prospectus" && (
                    <p className={styles.muted}>招股说明书未可靠披露该机构的公开联系字段。</p>
                  )}
                </div>

                <div className={styles.actions}>
                  <Link href={starInvestorInstitutionHref(record)}>
                    {directoryInstitution ? "查看匹配的机构档案" : "在机构目录中检索"}
                  </Link>
                  {directoryInstitution?.officialUrl && (
                    <a href={directoryInstitution.officialUrl} target="_blank" rel="noreferrer">
                      机构官网 <ArrowUpRight size={12} />
                    </a>
                  )}
                  <a href={prospectusPage} target="_blank" rel="noreferrer">
                    核对招股书原页 <FileText size={12} />
                  </a>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <section className={styles.empty}>
          <ShieldCheck size={26} />
          <strong>当前筛选没有质量门后候选记录</strong>
          <p>被判定为句子碎片、通用法律形式、证据数值冲突或上市公司自身名称的记录不会展示。</p>
        </section>
      )}

      <p className={styles.disclosure}>
        人工决定由版本化审核清单按“公司 slug：候选 ID”记录审核人、时间和说明。持股字段只接受候选名称之后同一证据行中的唯一数值；未经清单明确核验的候选不展示机构联系方式。
      </p>
    </div>
  );
}
