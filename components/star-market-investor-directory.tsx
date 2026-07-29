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
  if (value === undefined || !Number.isFinite(value)) return "未披露";
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
      <section className={styles.stats} aria-label="科创板投资人目录统计">
        <div><span>科创板公司</span><strong>{starMarketInvestorStats.companies}</strong></div>
        <div><span>机构投资人</span><strong>{starMarketInvestorStats.investors}</strong></div>
        <div><span>已关联机构目录</span><strong>{starMarketInvestorStats.linkedInstitutions}</strong></div>
        <div><span>招股书披露联系渠道</span><strong>{starMarketInvestorStats.prospectusContacts}</strong></div>
      </section>

      <div className={styles.filters}>
        <label className={styles.search}>
          <Search size={15} aria-hidden="true" />
          <input
            aria-label="搜索科创板投资人"
            placeholder="搜索机构、上市公司、代码或赛道"
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
          仅显示招股书披露联系渠道
        </label>
        <span className={styles.count}>显示 {filtered.length} 条</span>
      </div>

      {filtered.length ? (
        <section className={styles.grid} aria-label="科创板机构投资人名单">
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
                      投资于 {listedCompany.name}（{listedCompany.ticker}）
                    </p>
                  </div>
                </div>

                <dl className={styles.holdings}>
                  <div>
                    <dt>发行前持股</dt>
                    <dd>{numberLabel(investor.preIpoShares)}</dd>
                  </div>
                  <div>
                    <dt>发行前比例</dt>
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

                <p className={styles.evidence}>{investor.evidence}</p>

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
                      <ArrowUpRight size={13} />招股书披露网站
                    </a>
                  )}
                  {!contact && (
                    <p className={styles.muted}>招股说明书未披露该机构的电话或邮箱。</p>
                  )}
                </div>

                <div className={styles.actions}>
                  <Link href={starInvestorInstitutionHref(record)}>
                    {directoryInstitution ? "查看投资机构档案" : "在机构目录中定位"}
                  </Link>
                  {directoryInstitution?.officialUrl && (
                    <a href={directoryInstitution.officialUrl} target="_blank" rel="noreferrer">
                      机构官网 <ArrowUpRight size={12} />
                    </a>
                  )}
                  <a href={prospectusPage} target="_blank" rel="noreferrer">
                    招股书原页 <FileText size={12} />
                  </a>
                </div>
              </article>
            );
          })}
        </section>
      ) : (
        <section className={styles.empty}>
          <ShieldCheck size={26} />
          <strong>当前筛选没有可公开的机构投资人记录</strong>
          <p>自然人股东及其私人联系方式不会进入该目录。</p>
        </section>
      )}

      <p className={styles.disclosure}>
        联系方式仅来自招股说明书明确披露的机构级信息；机构官网来自投资机构目录。自然人股东、手机号码、身份证件信息和家庭地址均不公开。
      </p>
    </div>
  );
}
