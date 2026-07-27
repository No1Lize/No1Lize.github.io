"use client";

import { Bookmark } from "lucide-react";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import styles from "@/components/homepage-favorite-controls.module.css";
import {
  FAVORITES_CHANGED_EVENT,
  FAVORITES_STORAGE_KEY,
  isFavorite,
  toggleFavorite,
  type FavoriteChannel,
  type FavoriteInput,
} from "@/lib/favorites";

type FavoriteMount = {
  element: HTMLElement;
  item: FavoriteInput;
};

type ChannelMeta = {
  channel: FavoriteChannel;
  channelLabel: string;
};

const channelByNumber: Record<string, ChannelMeta> = {
  "02": { channel: "technology", channelLabel: "新兴科技" },
  "03": { channel: "companies", channelLabel: "创业案例" },
  "04": { channel: "institutions", channelLabel: "投资机构" },
  "05": { channel: "ipo", channelLabel: "上市跟踪" },
  "06": { channel: "reports", channelLabel: "研究报告" },
  "07": { channel: "people", channelLabel: "人物研究" },
};

function cleanText(value: string | null | undefined): string {
  return (value ?? "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function hrefFrom(anchor: HTMLAnchorElement | null): string {
  if (!anchor) return "";
  const raw = cleanText(anchor.getAttribute("href"));
  if (raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return cleanText(anchor.href || raw);
}

function stableId(title: string, href: string): string {
  const input = `article|${title}|${href}`;
  let hash = 2166136261;
  for (let index = 0; index < input.length; index += 1) {
    hash ^= input.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `homepage:article:${(hash >>> 0).toString(36)}`;
}

function inferChannel(label: string, context = ""): ChannelMeta {
  const combined = `${label} ${context}`;
  const numbered = combined.match(/(?:^|\s)(0[2-7])(?:\s|$)/)?.[1];
  if (numbered && channelByNumber[numbered]) return channelByNumber[numbered];
  if (/人物|采访|演讲|公开对话|观点|著作|股东信/.test(combined)) {
    return { channel: "people", channelLabel: "人物研究" };
  }
  if (/研报|报告|政策|公告/.test(combined)) {
    return { channel: "reports", channelLabel: "研究报告" };
  }
  if (/IPO|上市|招股|财报|监管文件/.test(combined)) {
    return { channel: "ipo", channelLabel: "上市跟踪" };
  }
  if (/融资|投资|并购|基金|资本/.test(combined)) {
    return { channel: "institutions", channelLabel: "投资机构" };
  }
  if (/技术|论文|模型|AI|芯片|机器人|产品发布/.test(combined)) {
    return { channel: "technology", channelLabel: "新兴科技" };
  }
  return { channel: "companies", channelLabel: "创业案例" };
}

function regionFrom(values: string[]): "中国" | "美国" | "全球" | undefined {
  if (values.some((value) => value.includes("中国"))) return "中国";
  if (values.some((value) => value.includes("美国") || value.includes("美股"))) return "美国";
  if (values.some((value) => value.includes("全球"))) return "全球";
  return undefined;
}

function publishedAtFrom(row: HTMLElement): string | undefined {
  const monthDay = cleanText(row.querySelector<HTMLElement>(".event-date strong")?.textContent);
  const year = cleanText(row.querySelector<HTMLElement>(".event-date span")?.textContent);
  const date = `${year}-${monthDay}`;
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : undefined;
}

function makeEventFavorite(row: HTMLElement): FavoriteInput | null {
  const title = cleanText(row.querySelector("h3")?.textContent);
  const summary = cleanText(row.querySelector(".event-main > p")?.textContent);
  const sourceLink = row.querySelector<HTMLAnchorElement>("a.source-link");
  const titleLink = row.querySelector<HTMLAnchorElement>("h3 a[href]");
  const href = hrefFrom(sourceLink) || hrefFrom(titleLink);
  if (!title || !href) return null;

  const tags = [...row.querySelectorAll<HTMLElement>(".event-tags span")]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const eventType = tags[0] ?? "公司动态";
  const channel = inferChannel(eventType, tags.join(" "));
  const sourceName = cleanText(sourceLink?.textContent) || "公开信源";
  const region = regionFrom(tags);
  const importanceRaw = cleanText(row.querySelector<HTMLElement>(".importance strong")?.textContent);
  const importance = Number(importanceRaw);
  const publishedAt = publishedAtFrom(row);

  return {
    id: stableId(title, href),
    href,
    title,
    summary,
    ...channel,
    keywords: tags,
    sectors: tags.slice(2),
    sources: [{ name: sourceName, url: href, level: eventType }],
    ...(region ? { region } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(Number.isFinite(importance) ? { importance } : {}),
    eventType,
  };
}

function makeFeedFavorite(row: HTMLAnchorElement): FavoriteInput | null {
  const title = cleanText(row.querySelector<HTMLElement>("[class*='feedTitle']")?.textContent);
  const context = cleanText(row.querySelector<HTMLElement>("[class*='feedContext']")?.textContent);
  const tag = cleanText(row.querySelector<HTMLElement>("[class*='feedTag']")?.textContent);
  const aside = [...row.querySelectorAll<HTMLElement>("[class*='feedAside'] span")]
    .map((element) => cleanText(element.textContent))
    .filter(Boolean);
  const href = hrefFrom(row);
  if (!title || !href) return null;

  const channel = inferChannel(tag || aside[1] || "", context);
  const sourceName = cleanText(context.replace(tag, "").replace(/^·|·$/g, "")) || "公开信源";
  const region = regionFrom([context, tag, ...aside]);
  const publishedAt = aside.find((value) => /^\d{4}-\d{2}-\d{2}$/.test(value));

  return {
    id: stableId(title, href),
    href,
    title,
    summary: context || "从首页收藏的公开情报条目。",
    ...channel,
    keywords: [tag, ...aside].filter(Boolean),
    sectors: [],
    sources: href.startsWith("http") ? [{ name: sourceName, url: href }] : [],
    ...(region ? { region } : {}),
    ...(publishedAt ? { publishedAt } : {}),
    ...(tag ? { eventType: tag } : {}),
  };
}

function InlineFavoriteButton({ item }: { item: FavoriteInput }) {
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const refresh = () => setSaved(isFavorite(item.id));
    const onStorage = (event: StorageEvent) => {
      if (event.key === FAVORITES_STORAGE_KEY) refresh();
    };
    refresh();
    window.addEventListener(FAVORITES_CHANGED_EVENT, refresh);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(FAVORITES_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", onStorage);
    };
  }, [item.id]);

  return (
    <button
      type="button"
      className={styles.button}
      data-saved={saved ? "true" : "false"}
      aria-pressed={saved}
      aria-label={saved ? `取消收藏：${item.title}` : `收藏：${item.title}`}
      title={saved ? "取消收藏" : "收藏这条情报到 08 收藏频道"}
      onMouseDown={(event) => {
        event.preventDefault();
        event.stopPropagation();
      }}
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        setSaved(toggleFavorite(item));
      }}
    >
      <Bookmark size={12} fill={saved ? "currentColor" : "none"} />
      <span>{saved ? "已收藏" : "收藏"}</span>
    </button>
  );
}

export function HomepageFavoriteControls() {
  const [mounts, setMounts] = useState<FavoriteMount[]>([]);

  useEffect(() => {
    const created: HTMLElement[] = [];

    const clearMounts = () => {
      created.splice(0).forEach((element) => element.remove());
      document
        .querySelectorAll<HTMLElement>("[data-homepage-favorite-mount='true']")
        .forEach((element) => element.remove());
    };

    const addMount = (
      target: HTMLElement,
      item: FavoriteInput,
      placement: "event" | "feed",
    ) => {
      const element = document.createElement("span");
      element.dataset.homepageFavoriteMount = "true";
      element.className = `${styles.mount} ${placement === "event" ? styles.eventMount : styles.feedMount}`;
      if (placement === "event") target.prepend(element);
      else target.appendChild(element);
      created.push(element);
      return { element, item };
    };

    const scan = () => {
      clearMounts();
      const next: FavoriteMount[] = [];

      document.querySelectorAll<HTMLElement>(".event-row").forEach((row) => {
        const item = makeEventFavorite(row);
        const target = row.querySelector<HTMLElement>(".importance");
        if (item && target) next.push(addMount(target, item, "event"));
      });

      document
        .querySelectorAll<HTMLAnchorElement>(".headlines-column a[class*='feedRow']")
        .forEach((row) => {
          const item = makeFeedFavorite(row);
          const target = row.querySelector<HTMLElement>("[class*='feedContext']");
          if (item && target) next.push(addMount(target, item, "feed"));
        });

      document
        .querySelectorAll<HTMLAnchorElement>(".side-column a[class*='feedRow']")
        .forEach((row) => {
          const item = makeFeedFavorite(row);
          const target = row.querySelector<HTMLElement>("[class*='feedContext']");
          if (item && target) next.push(addMount(target, item, "feed"));
        });

      setMounts(next);
    };

    scan();

    const eventList = document.querySelector(".event-list");
    const observer = eventList
      ? new MutationObserver(() => window.requestAnimationFrame(scan))
      : null;
    observer?.observe(eventList, { childList: true });

    return () => {
      observer?.disconnect();
      clearMounts();
    };
  }, []);

  return (
    <>
      {mounts.map(({ element, item }) =>
        createPortal(<InlineFavoriteButton item={item} />, element, item.id),
      )}
    </>
  );
}
