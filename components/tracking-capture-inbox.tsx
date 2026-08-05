"use client";

import { BookOpen, ExternalLink, Inbox, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import rawInbox from "@/config/tracking_capture_inbox.json";
import { base64ToText } from "@/lib/github-commit";
import { trackingEntityResearchHref } from "@/lib/tracking-entity-route";
import {
  TRACKING_BRANCH,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import {
  TRACKING_CAPTURE_CHANGED_EVENT,
  TRACKING_CAPTURE_INBOX_PATH,
  normalizeTrackingCaptureInbox,
  type TrackingCaptureEntityType,
  type TrackingCaptureInbox,
  type TrackingCaptureStatus,
} from "@/lib/tracking-capture";
import styles from "./tracking-capture-inbox.module.css";

type InboxFilter = "all" | TrackingCaptureStatus;

const ENTITY_LABELS: Record<TrackingCaptureEntityType, string> = {
  company: "公司",
  person: "人物",
  topic: "技术／主题",
};

const STATUS_LABELS: Record<TrackingCaptureStatus, string> = {
  queued: "等待应用",
  applied: "已开始追踪",
  dismissed: "已忽略",
};

const ATTENTION_LABELS = {
  1: "仅记录",
  2: "新闻提醒",
  3: "一般跟踪",
  4: "重点观察",
  5: "核心研究",
} as const;

function formatTime(value: string): string {
  if (!value) return "时间未记录";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

async function fetchLatestInbox(): Promise<TrackingCaptureInbox> {
  const url = `https://api.github.com/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CAPTURE_INBOX_PATH}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`;
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!response.ok) throw new Error(`GitHub API returned ${response.status}`);
  const file = (await response.json()) as { content?: string };
  if (!file.content) throw new Error("GitHub API did not return capture inbox content");
  return normalizeTrackingCaptureInbox(JSON.parse(base64ToText(file.content)));
}

export function TrackingCaptureInbox() {
  const [inbox, setInbox] = useState(() => normalizeTrackingCaptureInbox(rawInbox));
  const [filter, setFilter] = useState<InboxFilter>("all");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState("正在使用构建快照；页面载入后会读取 main 的最新采集箱。");

  async function reload() {
    setLoading(true);
    try {
      const latest = await fetchLatestInbox();
      setInbox(latest);
      setStatus(`已读取 main 的最新采集箱，共 ${latest.records.length} 条。`);
    } catch (error) {
      setStatus(`读取最新采集箱失败，继续显示构建快照：${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => void reload(), 0);
    const onChanged = () => void reload();
    window.addEventListener(TRACKING_CAPTURE_CHANGED_EVENT, onChanged);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener(TRACKING_CAPTURE_CHANGED_EVENT, onChanged);
    };
  }, []);

  const counts = useMemo(() => {
    const result = { all: inbox.records.length, queued: 0, applied: 0, dismissed: 0 };
    for (const record of inbox.records) result[record.status] += 1;
    return result;
  }, [inbox.records]);

  const visible = useMemo(
    () =>
      inbox.records.filter((record) => filter === "all" || record.status === filter),
    [filter, inbox.records],
  );

  return (
    <section className={styles.shell} id="tracking-capture-inbox">
      <header className={styles.header}>
        <div>
          <p className="section-index">ARTICLE CAPTURE INBOX</p>
          <div className={styles.titleLine}>
            <Inbox size={20} aria-hidden="true" />
            <h2>文章采集箱</h2>
          </div>
          <p>
            保存从主频道文章中人工发现的公司、人物和技术／主题，并记录原文、目标赛道、操作人和 GitHub 审计历史。
            公司采集会进入候选审核，不会绕过正式建档质量门。
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link href="/tracking/entities" className={styles.libraryLink}>
            <BookOpen size={15} />追踪对象研究库
          </Link>
          <button type="button" className={styles.reload} disabled={loading} onClick={reload}>
            <RefreshCw className={loading ? styles.spinning : undefined} size={15} />
            重新载入
          </button>
        </div>
      </header>

      <div className={styles.metrics}>
        <div><span>全部</span><strong>{counts.all}</strong></div>
        <div><span>已开始追踪</span><strong>{counts.applied}</strong></div>
        <div><span>等待应用</span><strong>{counts.queued}</strong></div>
        <div><span>已忽略</span><strong>{counts.dismissed}</strong></div>
      </div>

      <div className={styles.filters} aria-label="文章采集箱筛选">
        {(
          [
            ["all", "全部"],
            ["applied", "已开始追踪"],
            ["queued", "等待应用"],
            ["dismissed", "已忽略"],
          ] as const
        ).map(([value, label]) => (
          <button
            type="button"
            key={value}
            data-active={filter === value}
            onClick={() => setFilter(value)}
          >
            {label} {counts[value]}
          </button>
        ))}
      </div>

      <p className={styles.status} aria-live="polite">{status}</p>

      <div className={styles.list}>
        {visible.map((record) => (
          <article className={styles.card} key={record.id}>
            <div className={styles.cardTop}>
              <div>
                <span data-entity={record.entityType}>{ENTITY_LABELS[record.entityType]}</span>
                <strong>{record.canonicalName}</strong>
              </div>
              <em data-status={record.status}>{STATUS_LABELS[record.status]}</em>
            </div>
            <dl>
              <div>
                <dt>目标赛道</dt>
                <dd>{record.trackNames.join(" / ") || record.trackSlugs.join(" / ") || "未记录"}</dd>
              </div>
              <div>
                <dt>应用位置</dt>
                <dd>{record.appliedTo.join("、") || "等待下一次同步"}</dd>
              </div>
              <div>
                <dt>关注等级</dt>
                <dd>{record.attentionLevel} 星 · {ATTENTION_LABELS[record.attentionLevel]}</dd>
              </div>
              <div>
                <dt>操作审计</dt>
                <dd>{record.capturedBy || "未知管理员"} · {formatTime(record.capturedAt)}</dd>
              </div>
            </dl>
            {record.reasons.length || record.note ? (
              <div className={styles.researchMeta}>
                {record.reasons.length ? (
                  <div>{record.reasons.map((reason) => <span key={reason}>{reason}</span>)}</div>
                ) : null}
                {record.note ? <p>{record.note}</p> : null}
              </div>
            ) : null}
            <div className={styles.source}>
              <div>
                <span>{record.source.channelLabel || record.source.channel} · {record.source.eventType}</span>
                <strong>{record.source.title}</strong>
                <p>{record.source.summary || "未保存摘要。"}</p>
              </div>
              <div className={styles.sourceActions}>
                <Link href={trackingEntityResearchHref(record.entityType, record.canonicalName)}>
                  研究页 <BookOpen size={13} />
                </Link>
                <a href={record.source.url} target="_blank" rel="noreferrer">
                  原文 <ExternalLink size={13} />
                </a>
              </div>
            </div>
          </article>
        ))}
        {!visible.length ? (
          <div className={styles.empty}>
            <Inbox size={22} />
            <strong>当前筛选下没有采集记录</strong>
            <p>在主频道文章卡片点击“＋追踪”后，记录会出现在这里。</p>
          </div>
        ) : null}
      </div>
    </section>
  );
}
