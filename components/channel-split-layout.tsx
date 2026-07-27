import type { ReactNode } from "react";
import { ChannelUpdateDirectory } from "@/components/channel-update-directory";
import type { ChannelUpdateKey } from "@/lib/channel-updates";
import styles from "./channel-split-layout.module.css";

type ChannelSplitLayoutProps = {
  channel: ChannelUpdateKey;
  eyebrow: string;
  title: string;
  description: string;
  count: number;
  countLabel: string;
  statusText?: string;
  icon: ReactNode;
  bodyClassName?: string;
  children: ReactNode;
};

export function ChannelSplitLayout({
  channel,
  eyebrow,
  title,
  description,
  count,
  countLabel,
  statusText = "持续更新",
  icon,
  bodyClassName,
  children,
}: ChannelSplitLayoutProps) {
  return (
    <div className={styles.splitLayout}>
      <div className={styles.updatesPanel}>
        <ChannelUpdateDirectory channel={channel} layout="split" />
      </div>

      <section className={styles.directoryPanel} aria-labelledby={`${channel}-directory-title`}>
        <header className={styles.panelHeader}>
          <div>
            <p className="section-index">{eyebrow}</p>
            <div className={styles.titleLine}>
              {icon}
              <h2 id={`${channel}-directory-title`}>{title}</h2>
            </div>
            <p className={styles.panelDescription}>{description}</p>
          </div>
          <div className={styles.snapshot}>
            <span>{countLabel}</span>
            <strong>{count}</strong>
            <small>{statusText}</small>
          </div>
        </header>

        <div className={`${styles.panelBody}${bodyClassName ? ` ${bodyClassName}` : ""}`}>
          {children}
        </div>
      </section>
    </div>
  );
}
