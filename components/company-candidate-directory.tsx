import { ArrowUpRight, Building2, ShieldCheck } from "lucide-react";
import {
  companyCandidateSnapshot,
  pendingCompanyCandidates,
} from "@/lib/company-candidate-data";
import styles from "./company-candidate-directory.module.css";

export function CompanyCandidateDirectory() {
  const visible = pendingCompanyCandidates.slice(0, 12);

  return (
    <section className={styles.section} aria-labelledby="company-candidates-title">
      <header className={styles.header}>
        <div>
          <p className="section-index">CANDIDATE COMPANY REVIEW</p>
          <div className={styles.titleLine}>
            <Building2 size={18} aria-hidden="true" />
            <h2 id="company-candidates-title">候选新公司</h2>
          </div>
          <p>
            仅使用结构化公司字段和可追溯来源生成。带人工操作审计记录、且实体解析无冲突的公司会自动免除二次人工复审；系统自动发现、来源无法证明为人工操作，或存在类型与身份歧义的对象才进入审核。正式公司档案仍须通过规范名称、slug、官方来源与质量门。
          </p>
        </div>
        <div className={styles.summary}>
          <span>需人工确认</span>
          <strong>{companyCandidateSnapshot.pendingCount}</strong>
          <small><ShieldCheck size={12} aria-hidden="true" /> 证据阈值 ≥ 35</small>
        </div>
      </header>

      {visible.length ? (
        <div className={styles.grid}>
          {visible.map((candidate) => (
            <article className={styles.card} key={candidate.id}>
              <div className={styles.cardTop}>
                <span>{candidate.region}</span>
                <b>评分 {candidate.score}</b>
              </div>
              <h3>{candidate.name}</h3>
              <p>{candidate.sector} · {candidate.articleCount} 条记录 · {candidate.sourceCount} 个来源</p>
              <ul>
                {candidate.reasons.slice(0, 3).map((reason) => <li key={reason}>{reason}</li>)}
              </ul>
              <div className={styles.sources}>
                {candidate.sourceUrls.slice(0, 2).map((url, index) => (
                  <a href={url} key={url} rel="noreferrer" target="_blank">
                    来源 {index + 1}<ArrowUpRight size={13} aria-hidden="true" />
                  </a>
                ))}
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>
          <strong>当前没有需要人工确认的公司</strong>
          <p>具有人工审计来源且无冲突的新增公司会自动进入建档质量流程；自动发现和异常对象才会留在这里。</p>
        </div>
      )}
    </section>
  );
}
