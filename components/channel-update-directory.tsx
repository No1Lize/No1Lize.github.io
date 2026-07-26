import { ArrowUpRight, Clock3, RadioTower } from "lucide-react";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";
import styles from "./channel-update-directory.module.css";

export function ChannelUpdateDirectory({
  channel,
}: {
  channel: ChannelUpdateKey;
}) {
  const directory = getChannelUpdateDirectory(channel);
  const latestDate = directory.items[0]?.sortAt ?? "";
  const latestCount = latestDate
    ? directory.items.filter((item) => item.sortAt === latestDate).length
    : 0;

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
          <span>公开资料快照</span>
          <strong>{directory.items.length}</strong>
          <small>
            <Clock3 size={12} aria-hidden="true" />
            {directory.generatedAt.slice(0, 10) || "等待更新"}
          </small>
        </div>
      </div>

      {directory.items.length ? (
        <div className={styles.list}>
          {directory.items.map((item, index) => (
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
                  <time>{item.date}</time>
                  {item.sortAt === latestDate && (
                    <b>{latestCount > 1 ? `本轮新增 ${latestCount}` : "本轮新增"}</b>
                  )}
                </div>
                <h3>{item.title}</h3>
                <p>{item.summary}</p>
                <small>
                  {item.context} · {item.source}
                </small>
              </div>
              <ArrowUpRight className={styles.arrow} size={18} aria-hidden="true" />
            </a>
          ))}
        </div>
      ) : (
        <div className={styles.empty}>
          <strong>尚未发现可展示的更新</strong>
          <p>下一次数据抓取完成后，新记录会自动出现在这里。</p>
        </div>
      )}
    </section>
  );
}
