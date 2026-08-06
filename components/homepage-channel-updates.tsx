import { HomepageSortableFeed } from "@/components/homepage-sortable-feed";
import styles from "@/components/homepage-columns.module.css";
import { coreTechnologyEntities } from "@/lib/core-research-objects";
import { HOMEPAGE_CHANNEL_UPDATE_LIMIT } from "@/lib/homepage-channel-update-config";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateItem,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";
import rawArticles from "@/public/data/articles.json";

const homepageChannels = [
  { key: "technologies", number: "02", label: "核心技术", href: "/technologies" },
  { key: "technology", number: "03", label: "核心赛道", href: "/technology" },
  { key: "people", number: "04", label: "核心人物", href: "/people" },
  { key: "companies", number: "05", label: "核心公司", href: "/companies" },
] as const satisfies ReadonlyArray<{
  key: "technologies" | ChannelUpdateKey;
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

function coreTechnologyUpdates(): ChannelUpdateItem[] {
  return coreTechnologyEntities.flatMap((entity) =>
    entity.timeline.flatMap((timeline) => {
      const href = timeline.url.trim();
      if (!href) return [];
      const dateOriginal = timeline.eventDate || timeline.observedAt;
      const date = dateOriginal.slice(0, 10);
      return [
        {
          id: `technology:${entity.id}:${timeline.id}`,
          title: timeline.title,
          summary: timeline.summary,
          href,
          source: timeline.sourceName || "VCIQ",
          label: timeline.eventType || "技术动态",
          context: [entity.name, ...entity.trackNames.slice(0, 2)].join(" · "),
          date,
          dateOriginal,
          datePrecision: "exact" as const,
          sortAt: timeline.sortAt || dateOriginal,
          keywords: [entity.name, ...entity.trackNames],
          classifications: ["核心技术"],
        },
      ];
    }),
  );
}

function updatesForChannel(channel: HomepageChannel) {
  return channel.key === "technologies"
    ? coreTechnologyUpdates()
    : getChannelUpdateDirectory(channel.key).items;
}

function getChannelUpdates() {
  const updates = new Map<string, HomepageChannelUpdate>();

  homepageChannels.forEach((channel) => {
    updatesForChannel(channel).forEach((item) => {
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
    context: item.context || "研究对象更新",
    date: item.date,
    time: updateTime(item),
    asideLabel: item.label,
    sortAt: item.sortAt,
    importance: articleImportance.get(updateKey(item.href, item.title)) ?? 0,
  }));

  return (
    <aside className={`side-column ${styles.column}`} aria-label="核心研究对象最新更新">
      <div className="section-heading compact">
        <div>
          <p className="section-index">03 / OBJECT UPDATES</p>
          <h2>研究对象最新更新</h2>
        </div>
        <span>{Math.min(items.length, HOMEPAGE_CHANNEL_UPDATE_LIMIT)} 条</span>
      </div>

      <HomepageSortableFeed
        items={items}
        limit={HOMEPAGE_CHANNEL_UPDATE_LIMIT}
        ariaLabel="核心研究对象最新更新目录"
        initialSort="latest"
        description={`聚合核心技术、核心赛道、核心人物与核心公司，合并跨对象重复条目并展示前 ${HOMEPAGE_CHANNEL_UPDATE_LIMIT} 条；可切换按最新时间或重要性排序。`}
      />
    </aside>
  );
}
