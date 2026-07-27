"use client";

import {
  ArrowDownUp,
  ArrowUpRight,
  Clock3,
  RadioTower,
  Tags,
  Upload,
} from "lucide-react";
import { useId, useMemo, useRef, useState } from "react";
import type { DragEvent } from "react";
import { ChannelDocumentImport } from "@/components/channel-document-import";
import {
  ALL_CHANNEL_UPDATE_KEYWORDS,
  collectChannelUpdateKeywords,
  filterAndSortChannelUpdates,
  type ChannelUpdateSortOrder,
} from "@/lib/channel-update-filter";
import type {
  ChannelUpdateDirectory,
  ChannelUpdateItem,
  ChannelUpdateKey,
} from "@/lib/channel-updates";
import styles from "./channel-update-directory.module.css";

const channelLabels: Record<ChannelUpdateKey, string> = {
  technology: "新兴科技",
  companies: "创业案例",
  institutions: "投资机构",
  reports: "研究报告",
  people: "人物研究",
};

function hasDraggedFiles(event: DragEvent<HTMLElement>): boolean {
  return Array.from(event.dataTransfer?.types ?? []).includes("Files");
}

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
  const [importOpen, setImportOpen] = useState(false);
  const [incomingFiles, setIncomingFiles] = useState<File[] | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [localItems, setLocalItems] = useState<ChannelUpdateItem[]>([]);
  const dragDepthRef = useRef(0);

  const allItems = useMemo(() => {
    if (!localItems.length) return directory.items;
    const existing = new Set(directory.items.map((item) => item.id));
    return [
      ...localItems.filter((item) => !existing.has(item.id)),
      ...directory.items,
    ];
  }, [directory.items, localItems]);
  const localIds = useMemo(
    () => new Set(localItems.map((item) => item.id)),
    [localItems],
  );

  const eventTypeOptions = useMemo(
    () => collectChannelUpdateKeywords(allItems),
    [allItems],
  );
  const visibleItems = useMemo(
    () =>
      filterAndSortChannelUpdates({
        items: allItems,
        keyword,
        sortOrder,
      }),
    [allItems, keyword, sortOrder],
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

  function onDragEnter(event: DragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    dragDepthRef.current += 1;
    setDragActive(true);
  }

  function onDragOver(event: DragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
  }

  function onDragLeave(event: DragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setDragActive(false);
  }

  function onDrop(event: DragEvent<HTMLElement>) {
    if (!hasDraggedFiles(event)) return;
    event.preventDefault();
    dragDepthRef.current = 0;
    setDragActive(false);
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (!files.length) return;
    setIncomingFiles(files);
    setImportOpen(true);
  }

  return (
    <section
      className={styles.directory}
      aria-labelledby={`${channel}-updates-title`}
      data-drag-active={dragActive || undefined}
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
    >
      {dragActive && (
        <div className={styles.dropOverlay} aria-hidden="true">
          <Upload size={22} />
          <strong>松开文件，导入到{directory.title}</strong>
          <span>支持 PDF / Word / PPT / 文本 / 图片</span>
        </div>
      )}

      <div className={styles.header}>
        <div className={styles.heading}>
          <p className="section-index">LATEST CRAWLED UPDATES</p>
          <div className={styles.titleLine}>
            <RadioTower size={19} aria-hidden="true" />
            <h2 id={`${channel}-updates-title`}>{directory.title}</h2>
          </div>
          <p>{directory.description}</p>
          <button
            type="button"
            className={styles.importToggle}
            onClick={() => setImportOpen((open) => !open)}
          >
            <Upload size={13} aria-hidden="true" />
            {importOpen ? "收起导入面板" : "导入文档信源（拖拽 / Ctrl+V）"}
          </button>
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

      <ChannelDocumentImport
        channel={channel}
        open={importOpen}
        incomingFiles={incomingFiles}
        onIncomingConsumed={() => setIncomingFiles(null)}
        onClose={() => setImportOpen(false)}
        onSaved={(item) =>
          setLocalItems((previous) => [
            item,
            ...previous.filter((existing) => existing.id !== item.id),
          ])
        }
      />

      {allItems.length ? (
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
                  全部事件（{allItems.length}）
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
                    data-intelligence-item="true"
                    data-intelligence-title={item.title}
                    data-intelligence-summary={item.summary}
                    data-intelligence-type={item.label}
                    data-intelligence-date={
                      item.datePrecision === "undated" ? undefined : item.sortAt
                    }
                    data-intelligence-source={item.source}
                    data-intelligence-source-level={item.label}
                    data-intelligence-context={item.context}
                    data-intelligence-keywords={item.keywords.join("|")}
                    data-intelligence-channel={channel}
                    data-intelligence-channel-label={channelLabels[channel]}
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
                        {localIds.has(item.id) && <i>已提交 · 等待站点重建</i>}
                        {item.id === latestDatedItemId && <b>时间最新</b>}
                      </div>
                      <h3 data-intelligence-title>{item.title}</h3>
                      <p data-intelligence-summary>{item.summary}</p>
                      <small data-intelligence-source>
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
          <p>下一次数据抓取完成后，新记录会自动出现在这里；也可以通过上方导入面板添加本地文档信源。</p>
        </div>
      )}
    </section>
  );
}
