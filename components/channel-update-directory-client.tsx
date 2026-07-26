"use client";

import { ArrowDownUp, ArrowUpRight, Clock3, RadioTower, Tags } from "lucide-react";
import { useId, useMemo, useState } from "react";
import {
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateKeywords,
  filterAndSortChannelUpdates,
  type ChannelUpdateSortOrder,
} from "@/lib/channel-update-filter";
import type {
  ChannelUpdateDirectory,
  ChannelUpdateKey,
} from "@/lib/channel-updates";
import styles from "./channel-update-directory.module.css";

export function ChannelUpdateDirectoryClient({
  channel,
  directory,
}: {
  channel: ChannelUpdateKey;
  directory: ChannelUpdateDirectory;
}) {
  const eventTypeSelectId = useId();
  const sortSelectId = useId();
  const [keyword, setKeyword] = useState(ALL_CHANNEL_UPDATE_KEYWORDS);
  const [sortOrder, setSortOrder] = useState<ChannelUpdateSortOrder>("newest");
  const eventTypeOptions = useMemo(
    () => collectChannelUpdateKeywords(directory.items),
    [directory.items],
  );
  const visibleItems = useMemo(
    () =>
      filterAndSortChannelUpdates({
        items: directory.items,
        keyword,
        sortOrder,
      }),
    [directory.items, keyword, sortOrder],
  );
  const latestDatedItemId = useMemo(() => {
    let latest: (typeof visibleItems)[number] | undefined;
    for (const item of visibleItems) {
      if (item.datePrecision === "undated") continue;
      if (!latest || item.sortAt > latest.sortAt) latest = item;
    }
    return latest?.id ?? "";
  }, [visibleItems]);
  const isFiltered = keyword !== ALL_CHANNEL_UPDATE_KEYWORDS;

  return (
    <section className={styles.directory} aria-labelledby={`${channel}-updates-title`}>
      <div className={styles.header}>
        <div className={styles.heading}>
          <p className="section-index">LATEST CRAWLED UPDATES</p>
          <div className={styles.titleLine}>
            <RadioTower size={19} aria-hidden="true" />
            <h2 id={`${channel}-updates-title`}>{directory.title}</h2>
          </div>
          <p>{directory.description}</p>
        </div>
        <div className={styles.snapshot}>
          <span>{isFiltered ? "筛选结果" : "公开资料快照"}</span>
          <strong>{visibleItems.length}</strong>
          <small>
            <Clock3 size={12} aria-hidden="true" />
            {directory.generatedAt.slice(0, 10) || "等待更新"}
          </small>
        </div>
      </div>

      {directory.items.length ? (
        <>
          <div className={styles.controls}>
            <div className={styles.controlIntro}>
              <Tags size={17} aria-hidden="true" />
              <div>
                <strong>按事件类型筛选</strong>
                <span>筛选项只使用每条记录前面的绿色标签，结果按标准化日期排序。</span>
              </div>
            </div>

            <label className={styles.control} htmlFor={eventTypeSelectId}>
              <span>事件类型</span>
              <select
                id={eventTypeSelectId}
                value={keyword}
                onChange={(event) => setKeyword(event.target.value)}
              >
                <option value={ALL_CHANNEL_UPDATE_KEYWORDS}>
                  全部事件（{directory.items.length}）
                </option>
                {eventTypeOptions.map((option) => (
                  <option key={option.keyword} value={option.keyword}>
                    {option.keyword}（{option.count}）
                  </option>
                ))}
              </select>
            </label>

            <label className={styles.control} htmlFor={sortSelectId}>
              <span>时间排序</span>
              <select
                id={sortSelectId}
                value={sortOrder}
                onChange={(event) =>
                  setSortOrder(event.target.value as ChannelUpdateSortOrder)
                }
              >
                <option value="newest">最新优先</option>
                <option value="oldest">最早优先</option>
              </select>
            </label>

            <div className={styles.resultSummary} aria-live="polite">
              <ArrowDownUp size={14} aria-hidden="true" />
              <span>
                {isFiltered ? `“${keyword}” · ` : ""}
                {visibleItems.length} 条
              </span>
            </div>
          </div>

          {visibleItems.length ? (
            <div className={styles.list}>
              {visibleItems.map((item, index) => {
                const sourceDateTitle =
                  item.dateOriginal && item.dateOriginal !== item.date
                    ? `来源时间标注：${item.dateOriginal}`
                    : undefined;
                return (
                  <a
                    className={styles.item}
                    href={item.href}
                    key={item.id}
                    rel="noreferrer"
                    target="_blank"
                  >
                    <span className={styles.index}>
                      {String(index + 1).padStart(3, "0")}
                    </span>
                    <div className={styles.content}>
                      <div className={styles.meta}>
                        <span>{item.label}</span>
                        <time
                          dateTime={item.datePrecision === "undated" ? undefined : item.sortAt}
                          title={sourceDateTitle}
                        >
                          {item.date}
                        </time>
                        {item.id === latestDatedItemId && <b>时间最新</b>}
                      </div>
                      <h3>{item.title}</h3>
                      <p>{item.summary}</p>
                      <small>
                        {item.context} · {item.source}
                      </small>
                    </div>
                    <ArrowUpRight className={styles.arrow} size={18} aria-hidden="true" />
                  </a>
                );
              })}
            </div>
          ) : (
            <div className={styles.empty}>
              <strong>该事件类型下暂无更新</strong>
              <p>请选择其他事件类型，或切换回“全部事件”。</p>
            </div>
          )}
        </>
      ) : (
        <div className={styles.empty}>
          <strong>尚未发现可展示的更新</strong>
          <p>下一次数据抓取完成后，新记录会自动出现在这里。</p>
        </div>
      )}
    </section>
  );
}
