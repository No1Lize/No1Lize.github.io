import { HomepageSortableFeed } from "@/components/homepage-sortable-feed";
import styles from "@/components/homepage-columns.module.css";
import { HOMEPAGE_CHANNEL_UPDATE_LIMIT } from "@/lib/homepage-channel-update-config";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateItem,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";
import rawArticles from "@/public/data/articles.json";

const homepageChannels = [
  { key: "technology", number: "02", label: "新兴科技", href: "/technology" },
  { key: "companies", number: "03", label: "创业案例", href: "/companies" },
  { key: "institutions", number: "04", label: "投资机构", href: "/institutions" },
  { key: "reports", number: "06", label: "研究报告", href: "/reports" },
  { key: "people", number: "07", label: "人物研究", href: "/people" },
] as const satisfies ReadonlyArray<{
  key: ChannelUpdateKey;
  number: string;
  label: string;
  href: string;
}>;

type HomepageChannel = (typeof homepageChannels)[number];
type HomepageChannelUpdate = ChannelUpdateItem & {
  channels: HomepageChannel[];
};

type ArticlePayload = {
  articles?: Array<{
    title?: string;
    importance?: number;
    source?: { url?: string };
  }>;
};

function updateKey(href: string, title: string) {
  return `${href.trim().toLocaleLowerCase("en-US")}|${title
    .trim()
    .toLocaleLowerCase("zh-CN")}`;
}

const articleImportance = new Map(
  ((rawArticles as ArticlePayload).articles ?? []).flatMap((article) => {
    const href = article.source?.url?.trim() ?? "";
    const title = article.title?.trim() ?? "";
    if (!href || !title) return [];
    return [[updateKey(href, title), Number(article.importance ?? 0) || 0] as const];
  }),
);

function updateTime(item: ChannelUpdateItem): string {
  if (!/[T ]\d{2}:\d{2}/u.test(item.dateOriginal)) return "";
  const parsed = new Date(item.dateOriginal);
  if (Number.isNaN(parsed.getTime())) return "";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Taipei",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(parsed);
}

function getChannelUpdates() {
  const updates = new Map<string, HomepageChannelUpdate>();

  homepageChannels.forEach((channel) => {
    getChannelUpdateDirectory(channel.key).items.forEach((item) => {
      const key = updateKey(item.href, item.title);
      const existing = updates.get(key);

      if (existing) {
        if (!existing.channels.some((entry) => entry.key === channel.key)) {
          existing.channels.push(channel);
        }
        return;
      }

      updates.set(key, {
        ...item,
        channels: [channel],
      });
    });
  });

  return [...updates.values()];
}

export function HomepageChannelUpdates() {
  const updates = getChannelUpdates();
  const items = updates.map((item) => ({
    id: item.id,
    title: item.title,
    href: item.href,
    tag: item.channels.map((channel) => `${channel.number} ${channel.label}`).join(" / "),
    context: item.context || "频道内容更新",
    date: item.date,
    time: updateTime(item),
    asideLabel: item.label,
    sortAt: item.sortAt,
    importance: articleImportance.get(updateKey(item.href, item.title)) ?? 0,
  }));

  return (
    <aside className={`side-column ${styles.column}`} aria-label="频道最新更新">
      <div className="section-heading compact">
        <div>
          <p className="section-index">03 / CHANNEL UPDATES</p>
          <h2>频道最新更新</h2>
        </div>
        <span>{Math.min(items.length, HOMEPAGE_CHANNEL_UPDATE_LIMIT)} 条</span>
      </div>

      <HomepageSortableFeed
        items={items}
        limit={HOMEPAGE_CHANNEL_UPDATE_LIMIT}
        ariaLabel="频道最新更新目录"
        initialSort="latest"
        description={`聚合频道 02、03、04、06、07，合并跨频道重复条目并展示前 ${HOMEPAGE_CHANNEL_UPDATE_LIMIT} 条；可切换按最新时间或重要性排序。`}
      />
    </aside>
  );
}
