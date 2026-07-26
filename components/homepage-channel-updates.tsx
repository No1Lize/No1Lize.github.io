import { ArrowUpRight, ChevronRight } from "lucide-react";
import Link from "next/link";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateItem,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";

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

function getLatestChannelUpdates() {
  const updates = new Map<string, HomepageChannelUpdate>();

  homepageChannels.forEach((channel) => {
    getChannelUpdateDirectory(channel.key).items.forEach((item) => {
      const key = `${item.href.trim().toLocaleLowerCase("en-US")}|${item.title
        .trim()
        .toLocaleLowerCase("zh-CN")}`;
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

  return [...updates.values()]
    .sort(
      (left, right) =>
        right.sortAt.localeCompare(left.sortAt) ||
        right.date.localeCompare(left.date) ||
        left.title.localeCompare(right.title, "zh-CN"),
    )
    .slice(0, 15);
}

export function HomepageChannelUpdates() {
  const updates = getLatestChannelUpdates();

  return (
    <aside className="side-column">
      <div className="section-heading compact">
        <div>
          <p className="section-index">02 / CHANNEL UPDATES</p>
          <h2>频道最新更新</h2>
        </div>
        <span>{updates.length} 条</span>
      </div>

      <p className="method-note">
        聚合频道 02、03、04、06、07，按更新时间倒序排列，并合并跨频道重复条目。
      </p>

      <div className="heat-list" aria-label="频道最新更新目录">
        {updates.map((item, index) => (
          <a
            className="heat-row"
            href={item.href}
            key={`${item.id}-${item.href}`}
            target="_blank"
            rel="noreferrer"
          >
            <span className="heat-rank">{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong
                title={item.title}
                style={{
                  display: "-webkit-box",
                  WebkitBoxOrient: "vertical",
                  WebkitLineClamp: 2,
                  overflow: "hidden",
                }}
              >
                {item.title}
              </strong>
              <span title={item.context}>
                {item.channels.map((channel) => `${channel.number} ${channel.label}`).join(" / ")}
                {item.context ? ` · ${item.context}` : ""}
              </span>
            </div>
            <div>
              <span>{item.date}</span>
              <span>{item.label}</span>
            </div>
            <b aria-hidden="true"><ArrowUpRight size={14} /></b>
          </a>
        ))}
      </div>

      <nav aria-label="聚合频道入口">
        {homepageChannels.map((channel) => (
          <Link
            className="text-link"
            href={channel.href}
            key={channel.key}
            style={{ marginRight: 14 }}
          >
            {channel.number} {channel.label} <ChevronRight size={15} />
          </Link>
        ))}
      </nav>
    </aside>
  );
}
