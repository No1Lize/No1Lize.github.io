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
  starMarketInvestorCompanies,
  starMarketInvestorRecords,
  starMarketInvestorStats,
} from "@/lib/star-market-investor-data";
import styles from "./star-market-investor-directory.module.css";

function numberLabel(value?: number): string {
  if (value === undefined || !Number.isFinite(value)) return "未可靠提取";
  if (value >= 100_000_000) return `${(value / 100_000_000).toFixed(2)} 亿股`;
  if (value >= 10_000) return `${(value / 10_000).toFixed(2)} 万股`;
  return `${value.toLocaleString("zh-CN")} 股`;
}

export function StarMarketInvestorDirectory() {
  const [query, setQuery] = useState("");
  const [sector, setSector] = useState("全部赛道");
  const [company, setCompany] = useState("全部公司");
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
      if (contactOnly && record.investor.contactStatus !== "prospectus-public") return false;
      if (!needle) return true;
      const institution = record.directoryInstitution;
      return [
        record.investor.name,
        record.investor.investorType,
        record.company.name,
        record.company.ticker,
        record.company.sector,
        institution?.name,
        institution?.fullName,
      ]
        .filter(Boolean)
        .some((value) => String(value).toLocaleLowerCase("zh-CN").includes(needle));
    });
  }, [company, contactOnly, query, sector]);

  return (
    <div className={styles.directory}>
      <section className={styles.stats} aria-label="科创板招股说明书自动抽取统计">
        <div><span>已覆盖公司</span><strong>{starMarketInvestorStats.companies}</strong></div>
        <div><span>待核验抽取记录</span><strong>{starMarketInvestorStats.investors}</strong></div>
        <div><span>匹配站内机构</span><strong>{starMarketInvestorStats.linkedInstitutions}</strong></div>
        <div><span>含联系字段记录</span><strong>{starMarketInvestorStats.prospectusContacts}</strong></div>
      </section>

      <div className={styles.filters}>
        <label className={styles.search}>
          <Search size={15} aria-hidden="true" />
          <input
            aria-label="搜索自动抽取机构候选"
            placeholder="搜索候选名称、上市公司、代码或赛道"
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
        <label className={styles.checkbox}>
          <input
            type="checkbox"
            checked={contactOnly}
            onChange={(event) => setContactOnly(event.target.checked)}
          />
          仅显示自动关联联系字段
        </label>
        <span className={styles.count}>显示 {filtered.length} 条候选</span>
      </div>

      {filtered.length ? (
        <section className={styles.grid} aria-label="科创板招股说明书自动抽取候选记录">
          {filtered.map((record) => {
            const { investor, company: listedCompany, directoryInstitution } = record;
            const contact = investor.publicContact;
            const prospectusPage = `${listedCompany.prospectus.url}#page=${investor.sourcePage}`;
            return (
              <article className={styles.card} key={`${listedCompany.slug}:${investor.id}`}>
                <div className={styles.cardTop}>
                  <span>{investor.investorType}</span>
                  <span>{listedCompany.sector}</span>
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
                    <dt>抽取持股数</dt>
                    <dd>{numberLabel(investor.preIpoShares)}</dd>
                  </div>
                  <div>
                    <dt>抽取比例 · 待核验</dt>
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
                      <ArrowUpRight size={13} />招股书抽取网站字段
                    </a>
                  )}
                  {!contact && (
                    <p className={styles.muted}>未自动抽取到该候选记录的机构级联系字段。</p>
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
          <strong>当前筛选没有自动抽取候选记录</strong>
          <p>自然人股东及其私人联系方式不会进入该目录。</p>
        </section>
      )}

      <p className={styles.disclosure}>
        本目录为测试版自动抽取结果，不等同于经人工确认的机构股东名册。名称、持股字段和联系方式归属均应通过证据页及官方招股说明书核验；自然人股东、手机号码、身份证件信息和家庭地址不公开。
      </p>
    </div>
  );
}
