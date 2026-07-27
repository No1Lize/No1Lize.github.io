export type RefreshAudit = {
  mode?: string;
  pipelineCompleted?: boolean;
  completedAt?: string;
  localDate?: string;
  latestPublishedAt?: string;
  todayArticleCount?: number;
  todaySourceCount?: number;
};

export type SnapshotFreshness = {
  processedAt: string;
  label: "内置快照" | "数据异常" | "当日情报已更新" | "本轮抓取已完成" | "内容待刷新";
  description: string;
  stale: boolean;
};

export function formatTaipeiDate(value: string | Date): string {
  const timestamp = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return typeof value === "string" ? value.slice(0, 10) : "";
  }
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Taipei",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(timestamp);
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${values.year}-${values.month}-${values.day}`;
}

export function getSnapshotFreshness({
  isLive,
  generatedAt,
  latestPublishedAt,
  qualityPassed,
  refreshAudit,
  now = new Date(),
}: {
  isLive: boolean;
  generatedAt: string;
  latestPublishedAt: string;
  qualityPassed?: boolean;
  refreshAudit?: RefreshAudit;
  now?: Date;
}): SnapshotFreshness {
  const processedAt = formatTaipeiDate(generatedAt);
  const today = formatTaipeiDate(now);

  if (!isLive) {
    return {
      processedAt,
      label: "内置快照",
      description: "正在读取线上公开情报快照",
      stale: false,
    };
  }

  if (qualityPassed === false) {
    return {
      processedAt,
      label: "数据异常",
      description: "数据质量门未通过",
      stale: true,
    };
  }

  const auditDate = refreshAudit?.localDate ||
    (refreshAudit?.completedAt ? formatTaipeiDate(refreshAudit.completedAt) : "");
  const completedCurrentSnapshot =
    refreshAudit?.pipelineCompleted === true &&
    Boolean(auditDate) &&
    auditDate === processedAt;
  const processedToday = processedAt === today;
  const latestIsProcessedDay = latestPublishedAt === processedAt;

  if (completedCurrentSnapshot || processedToday) {
    if (latestIsProcessedDay) {
      return {
        processedAt,
        label: "当日情报已更新",
        description: "当前启用赛道的可追溯公开情报",
        stale: false,
      };
    }
    return {
      processedAt,
      label: "本轮抓取已完成",
      description: latestPublishedAt
        ? `本轮数据已处理，最新公开情报截至 ${latestPublishedAt}`
        : "本轮数据已处理，暂未发现可发布的新情报",
      stale: false,
    };
  }

  return {
    processedAt,
    label: "内容待刷新",
    description: latestPublishedAt
      ? `上次有效情报截至 ${latestPublishedAt}`
      : "尚未取得有效公开情报",
    stale: true,
  };
}
