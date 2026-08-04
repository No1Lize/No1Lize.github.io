import type { ChannelUpdateItem } from "./channel-updates";

export const ALL_CHANNEL_UPDATE_KEYWORDS = "全部";
export const ALL_CHANNEL_UPDATE_CLASSIFICATIONS = "全部分类";

export type ChannelUpdateSortOrder = "newest" | "oldest";

export type ChannelUpdateKeywordOption = {
  keyword: string;
  count: number;
};

function normalizeKeyword(value: string) {
  return value.trim().toLocaleLowerCase("zh-CN");
}

function snapshotDate(generatedAt: string) {
  const value = generatedAt.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/u.test(value) ? value : "";
}

export function countChannelUpdatesForSnapshotDay(
  items: ChannelUpdateItem[],
  generatedAt: string,
) {
  const date = snapshotDate(generatedAt);
  if (!date) return 0;

  return items.filter(
    (item) =>
      item.datePrecision !== "undated" &&
      item.sortAt.slice(0, 10) === date,
  ).length;
}

export function countChannelUpdatesFirstSeenForSnapshotDay(
  items: ChannelUpdateItem[],
  generatedAt: string,
) {
  const date = snapshotDate(generatedAt);
  if (!date) return 0;

  return items.filter(
    (item) =>
      Boolean(item.firstSeenAt) &&
      item.firstSeenEstimated !== true &&
      item.firstSeenAt?.slice(0, 10) === date,
  ).length;
}

function collectOptions(valuesByItem: string[][]): ChannelUpdateKeywordOption[] {
  const counts = new Map<string, { keyword: string; count: number }>();

  for (const values of valuesByItem) {
    const seenForItem = new Set<string>();
    for (const rawKeyword of values) {
      const keyword = rawKeyword.trim();
      const normalized = normalizeKeyword(keyword);
      if (!normalized || seenForItem.has(normalized)) continue;
      seenForItem.add(normalized);
      const current = counts.get(normalized);
      counts.set(normalized, {
        keyword: current?.keyword ?? keyword,
        count: (current?.count ?? 0) + 1,
      });
    }
  }

  return [...counts.values()].sort(
    (left, right) =>
      right.count - left.count || left.keyword.localeCompare(right.keyword, "zh-CN"),
  );
}

export function collectChannelUpdateKeywords(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => item.keywords));
}

export function collectChannelUpdateClassifications(
  items: ChannelUpdateItem[],
): ChannelUpdateKeywordOption[] {
  return collectOptions(items.map((item) => item.classifications ?? []));
}

export function filterAndSortChannelUpdates({
  items,
  keyword,
  classification = ALL_CHANNEL_UPDATE_CLASSIFICATIONS,
  sortOrder,
}: {
  items: ChannelUpdateItem[];
  keyword: string;
  classification?: string;
  sortOrder: ChannelUpdateSortOrder;
}) {
  const normalizedKeyword = normalizeKeyword(keyword);
  const normalizedClassification = normalizeKeyword(classification);
  const filtered = items.filter((item) => {
    const keywordMatches =
      keyword === ALL_CHANNEL_UPDATE_KEYWORDS ||
      item.keywords.some(
        (itemKeyword) => normalizeKeyword(itemKeyword) === normalizedKeyword,
      );
    const classificationMatches =
      classification === ALL_CHANNEL_UPDATE_CLASSIFICATIONS ||
      (item.classifications ?? []).some(
        (itemClassification) =>
          normalizeKeyword(itemClassification) === normalizedClassification,
      );
    return keywordMatches && classificationMatches;
  });

  return filtered.sort((left, right) => {
    const dateComparison =
      sortOrder === "newest"
        ? right.sortAt.localeCompare(left.sortAt) || right.date.localeCompare(left.date)
        : left.sortAt.localeCompare(right.sortAt) || left.date.localeCompare(right.date);
    return dateComparison || left.title.localeCompare(right.title, "zh-CN");
  });
}
