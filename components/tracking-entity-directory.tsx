"use client";

import Link from "next/link";
import { Building2, Cpu, Search, UserRound } from "lucide-react";
import { useMemo, useState } from "react";
import type {
  TrackingResearchEntityState,
  TrackingResearchEntityType,
} from "@/lib/tracking-entity-research";
import styles from "./tracking-entity-directory.module.css";

export type TrackingEntityDirectoryItem = {
  id: string;
  entityType: TrackingResearchEntityType;
  slug: string;
  name: string;
  aliases: string[];
  trackNames: string[];
  state: TrackingResearchEntityState;
  formalLabel: string;
  candidateStatus: string;
  summary: string;
  firstTrackedAt: string;
  lastActivityAt: string;
  captureCount: number;
  articleCount: number;
  reasons: string[];
  priority: number;
  priorityLabel: string;
  priorityStars: string;
};

type TypeFilter = "all" | TrackingResearchEntityType;
type StateFilter = "all" | TrackingResearchEntityState;
type SortOrder = "activity" | "name" | "evidence" | "priority";

const TYPE_LABELS: Record<TrackingResearchEntityType, string> = {
  company: "公司",
  person: "人物",
  topic: "技术",
};

const STATE_LABELS: Record<TrackingResearchEntityState, string> = {
  formal: "已有正式档案",
  candidate: "候选审核中",
  tracked: "追踪中",
};

function TypeIcon({ type }: { type: TrackingResearchEntityType }) {
  if (type === "company") return <Building2 size={17} aria-hidden="true" />;
  if (type === "person") return <UserRound size={17} aria-hidden="true" />;
  return <Cpu size={17} aria-hidden="true" />;
}

function displayDate(value: string) {
  if (!value) return "尚无活动";
  const match = value.match(/^\d{4}-\d{2}-\d{2}/u);
  return match?.[0] ?? value;
}

export function TrackingEntityDirectory({
  items,
}: {
  items: TrackingEntityDirectoryItem[];
}) {
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState<TypeFilter>("all");
  const [stateFilter, setStateFilter] = useState<StateFilter>("all");
  const [sortOrder, setSortOrder] = useState<SortOrder>("activity");

  const visible = useMemo(() => {
    const normalizedQuery = query.normalize("NFKC").toLocaleLowerCase("zh-CN").trim();
    return items
      .filter((item) => typeFilter === "all" || item.entityType === typeFilter)
      .filter((item) => stateFilter === "all" || item.state === stateFilter)
      .filter((item) => {
        if (!normalizedQuery) return true;
        return [
          item.name,
          ...item.aliases,
          ...item.trackNames,
          ...item.reasons,
          item.summary,
        ]
          .join(" ")
          .normalize("NFKC")
          .toLocaleLowerCase("zh-CN")
          .includes(normalizedQuery);
      })
      .sort((left, right) => {
        if (sortOrder === "name") return left.name.localeCompare(right.name, "zh-CN");
        if (sortOrder === "priority") {
          return (
            right.priority - left.priority ||
            right.lastActivityAt.localeCompare(left.lastActivityAt)
          );
        }
        if (sortOrder === "evidence") {
          return (
            right.captureCount + right.articleCount - (left.captureCount + left.articleCount) ||
            right.lastActivityAt.localeCompare(left.lastActivityAt)
          );
        }
        return (
          right.lastActivityAt.localeCompare(left.lastActivityAt) ||
          left.name.localeCompare(right.name, "zh-CN")
        );
      });
  }, [items, query, sortOrder, stateFilter, typeFilter]);

  return (
    <>
      <div className={styles.filters}>
        <label className={styles.search}>
          <Search size={16} aria-hidden="true" />
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索公司、人物、技术、别名或赛道"
            aria-label="搜索追踪对象"
          />
        </label>
        <select
          value={typeFilter}
          onChange={(event) => setTypeFilter(event.target.value as TypeFilter)}
          aria-label="对象类型"
        >
          <option value="all">全部类型</option>
          <option value="company">公司</option>
          <option value="person">人物</option>
          <option value="topic">技术</option>
        </select>
        <select
          value={stateFilter}
          onChange={(event) => setStateFilter(event.target.value as StateFilter)}
          aria-label="档案状态"
        >
          <option value="all">全部状态</option>
          <option value="formal">已有正式档案</option>
          <option value="candidate">候选审核中</option>
          <option value="tracked">追踪中</option>
        </select>
        <select
          value={sortOrder}
          onChange={(event) => setSortOrder(event.target.value as SortOrder)}
          aria-label="排序方式"
        >
          <option value="activity">最近活动优先</option>
          <option value="priority">关注等级优先</option>
          <option value="evidence">证据数量优先</option>
          <option value="name">名称排序</option>
        </select>
        <span>共 {visible.length} 个追踪对象</span>
      </div>

      <div className={styles.grid}>
        {visible.map((item) => (
          <Link
            className={styles.card}
            href={`/tracking/entities/${item.entityType}/${item.slug}`}
            key={item.id}
          >
            <div className={styles.cardTop}>
              <span data-type={item.entityType}>
                <TypeIcon type={item.entityType} />
                {TYPE_LABELS[item.entityType]}
              </span>
              <div className={styles.cardStatus}>
                <em data-state={item.state}>{STATE_LABELS[item.state]}</em>
                {item.priority ? (
                  <small title={item.priorityLabel}>{item.priorityStars}</small>
                ) : null}
              </div>
            </div>
            <h2>{item.name}</h2>
            {item.aliases.length > 1 ? (
              <p className={styles.aliases}>{item.aliases.slice(1, 4).join(" · ")}</p>
            ) : null}
            <p>{item.summary}</p>
            <div className={styles.tracks}>
              {item.trackNames.slice(0, 4).map((track) => <span key={track}>{track}</span>)}
            </div>
            <dl>
              <div><dt>人工发现</dt><dd>{item.captureCount}</dd></div>
              <div><dt>公开动态</dt><dd>{item.articleCount}</dd></div>
              <div><dt>最近活动</dt><dd>{displayDate(item.lastActivityAt)}</dd></div>
            </dl>
          </Link>
        ))}
      </div>

      {!visible.length ? (
        <div className={styles.empty}>
          <Search size={22} aria-hidden="true" />
          <strong>没有匹配的追踪对象</strong>
          <p>调整对象类型、档案状态或搜索词。</p>
        </div>
      ) : null}
    </>
  );
}
