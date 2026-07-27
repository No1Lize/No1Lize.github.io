"use client";

import { useEffect, useMemo, useState, useSyncExternalStore } from "react";
import { createPortal } from "react-dom";
import {
  TrackingAdminRecommendation,
  type AdminRecommendationItem,
} from "@/components/tracking-admin-recommendation";
import { companies, ipoCompanies } from "@/lib/catalog-data";
import { sourceBrandKey } from "@/lib/source-brand";
import {
  DISMISSAL_EVENT,
  dismissTrackingRecommendation,
  hydrateTrackingRecommendationDismissals,
  isRecommendationDismissed,
} from "@/lib/tracking-recommendation-dismissal";
import {
  recommendListedCompanies,
  type ListedCompanyRecommendation,
} from "@/lib/tracking-listed-recommendations";
import {
  recommendTrackingAdditions,
  type TrackingSourceRecommendation,
} from "@/lib/tracking-recommendations";
import { useArticles } from "@/lib/use-articles";
import type { TrackingListedCompany } from "@/lib/user-tracking";

const LISTED_TITLE = "上市公司关注管理";
const SOURCE_TITLE = "补充信息源";

type Snapshot = {
  sector: string;
  listedKeys: string[];
  sourceUrls: string[];
};

function normalize(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("zh-CN");
}

function sectionByTitle(title: string): HTMLElement | null {
  return (
    Array.from(document.querySelectorAll<HTMLElement>("section")).find(
      (section) => section.querySelector("h2")?.textContent?.trim() === title,
    ) ?? null
  );
}

function currentSector(): string {
  const detailLabel = Array.from(document.querySelectorAll<HTMLElement>("p")).find(
    (node) => node.textContent?.trim() === "TRACK DETAIL",
  );
  const detail = detailLabel?.closest<HTMLElement>("section");
  return detail?.querySelector("h2")?.textContent?.trim() ?? "";
}

function ensureHost(section: HTMLElement, name: string): HTMLElement {
  const selector = `[data-admin-recommendation-host="${name}"]`;
  const existing = section.querySelector<HTMLElement>(selector);
  if (existing) return existing;
  const host = document.createElement("div");
  host.dataset.adminRecommendationHost = name;
  const help = Array.from(section.querySelectorAll<HTMLElement>("p")).find((item) =>
    item.className.includes("help"),
  );
  if (help?.nextSibling) help.parentElement?.insertBefore(host, help.nextSibling);
  else section.appendChild(host);
  return host;
}

function listedKeys(section: HTMLElement | null): string[] {
  if (!section) return [];
  const followedButtons = Array.from(section.querySelectorAll<HTMLButtonElement>("button"))
    .filter((button) => /·\s*(已关注|重新启用)/.test(button.textContent ?? ""))
    .map((button) => button.textContent ?? "");
  const followedCards = Array.from(section.querySelectorAll<HTMLElement>("article"))
    .filter((card) => /已有档案\s*\/\s*官方源|自定义/.test(card.textContent ?? ""))
    .map((card) => card.textContent ?? "");
  const text = normalize([...followedButtons, ...followedCards].join(" "));
  return ipoCompanies
    .filter(
      (company) =>
        text.includes(normalize(company.name)) && text.includes(normalize(company.ticker)),
    )
    .map((company) => `${company.market}:${company.ticker.toUpperCase()}`);
}

function sourceUrls(section: HTMLElement | null): string[] {
  if (!section) return [];
  return Array.from(section.querySelectorAll<HTMLElement>("span"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter((value) => /^https?:\/\//i.test(value));
}

function nativeSetInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function nativeSetSelectValue(select: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, "value")?.set;
  setter?.call(select, value);
  select.dispatchEvent(new Event("input", { bubbles: true }));
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

function labeledControl<T extends HTMLInputElement | HTMLSelectElement>(
  section: HTMLElement,
  labelText: string,
  selector: string,
): T | null {
  const label = Array.from(section.querySelectorAll<HTMLLabelElement>("label")).find((item) =>
    item.textContent?.trim().startsWith(labelText),
  );
  return label?.querySelector<T>(selector) ?? null;
}

function existingListedCompanies(keys: string[]): TrackingListedCompany[] {
  const allowed = new Set(keys);
  return ipoCompanies
    .filter((company) => allowed.has(`${company.market}:${company.ticker.toUpperCase()}`))
    .map((company) => ({
      id: `catalog-${company.slug}`,
      name: company.name,
      ticker: company.ticker,
      market: company.market,
      sector: company.sector,
      enabled: true,
      custom: false,
      catalogSlug: company.slug,
    }));
}

function fallbackSourceRecommendations(
  sector: string,
  existingUrls: string[],
): TrackingSourceRecommendation[] {
  const existingBrands = new Set(existingUrls.map(sourceBrandKey).filter(Boolean));
  return companies
    .filter((company) => normalize(company.sector) === normalize(sector))
    .filter((company) => {
      const brand = sourceBrandKey(company.source.url);
      return Boolean(brand && !existingBrands.has(brand));
    })
    .map((company) => ({
      value: company.source.url,
      label: `${company.name} 官方来源`,
      reason: `当前赛道官方公司来源 · 目录置信度 ${Math.round(company.confidence * 100)}%`,
      score: Math.round(company.confidence * 100),
      source: {
        name: `${company.name} 官方来源`,
        url: company.source.url,
        sourceType: "listing-search" as const,
        sourceCategory: "company" as const,
        region: company.region,
        sector,
        company: company.name,
        ticker: "",
        keywords: [company.name, sector],
      },
    }));
}

function mergeSources(
  primary: TrackingSourceRecommendation[],
  fallback: TrackingSourceRecommendation[],
  existingUrls: string[],
): TrackingSourceRecommendation[] {
  const existingBrands = new Set(existingUrls.map(sourceBrandKey).filter(Boolean));
  const merged = new Map<string, TrackingSourceRecommendation>();
  for (const item of [...primary, ...fallback]) {
    const key = sourceBrandKey(item.source.url);
    if (!key || existingBrands.has(key)) continue;
    const current = merged.get(key);
    if (!current || item.score > current.score) merged.set(key, item);
  }
  return [...merged.values()].sort(
    (left, right) => right.score - left.score || left.label.localeCompare(right.label),
  );
}

const emptyMountSubscribe = () => () => {};

export function TrackingAdminModuleRecommendations() {
  const { articles } = useArticles();
  // useSyncExternalStore-based mount probe avoids setState inside the
  // effect (client snapshot is true, server snapshot false).
  const mounted = useSyncExternalStore(
    emptyMountSubscribe,
    () => true,
    () => false,
  );
  const [dismissalVersion, setDismissalVersion] = useState(0);
  const [snapshot, setSnapshot] = useState<Snapshot>({
    sector: "",
    listedKeys: [],
    sourceUrls: [],
  });

  useEffect(() => {
    let frame = 0;
    let previous = "";
    const refresh = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const listedSection = sectionByTitle(LISTED_TITLE);
        const sourceSection = sectionByTitle(SOURCE_TITLE);
        sourceSection
          ?.querySelectorAll<HTMLElement>('[aria-label="智能推荐添加"]')
          .forEach((panel) => {
            panel.hidden = true;
          });
        const next = {
          sector: currentSector(),
          listedKeys: listedKeys(listedSection),
          sourceUrls: sourceUrls(sourceSection),
        };
        const serialized = JSON.stringify(next);
        if (serialized !== previous) {
          previous = serialized;
          setSnapshot(next);
        }
      });
    };
    const refreshDismissals = () => setDismissalVersion((value) => value + 1);
    const observer = new MutationObserver(refresh);
    observer.observe(document.body, { childList: true, subtree: true, attributes: true });
    window.addEventListener(DISMISSAL_EVENT, refreshDismissals);
    void hydrateTrackingRecommendationDismissals();
    refresh();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      window.removeEventListener(DISMISSAL_EVENT, refreshDismissals);
    };
  }, []);

  const listedRecommendations = useMemo(() => {
    if (!snapshot.sector) return [];
    return recommendListedCompanies(
      articles,
      snapshot.sector,
      ipoCompanies,
      existingListedCompanies(snapshot.listedKeys),
    ).filter(
      (item) =>
        !isRecommendationDismissed(
          snapshot.sector,
          "listedCompanies",
          item.value,
        ),
    );
  }, [articles, dismissalVersion, snapshot.listedKeys, snapshot.sector]);

  const sourceRecommendations = useMemo(() => {
    if (!snapshot.sector) return [];
    const discovered = recommendTrackingAdditions(articles, snapshot.sector, {
      sources: snapshot.sourceUrls,
    }).sources;
    return mergeSources(
      discovered,
      fallbackSourceRecommendations(snapshot.sector, snapshot.sourceUrls),
      snapshot.sourceUrls,
    ).filter(
      (item) =>
        !isRecommendationDismissed(snapshot.sector, "sources", item.value),
    );
  }, [articles, dismissalVersion, snapshot.sector, snapshot.sourceUrls]);

  async function addListed(item: ListedCompanyRecommendation) {
    const section = sectionByTitle(LISTED_TITLE);
    if (!section) throw new Error("未找到上市公司关注管理模块。");
    const search = section.querySelector<HTMLInputElement>(
      'input[placeholder="输入公司名称、股票代码、市场或赛道"]',
    );
    if (!search) throw new Error("未找到上市公司搜索框。");
    nativeSetInputValue(search, item.company.ticker);
    await nextFrame();
    await nextFrame();
    const button = Array.from(section.querySelectorAll<HTMLButtonElement>("button")).find(
      (candidate) => {
        const text = candidate.textContent ?? "";
        return text.includes(item.company.name) && text.includes(item.company.ticker);
      },
    );
    if (!button) throw new Error("推荐公司未出现在现有档案搜索结果中。");
    button.click();
  }

  async function addSource(item: TrackingSourceRecommendation) {
    const section = sectionByTitle(SOURCE_TITLE);
    if (!section) throw new Error("未找到补充信息源模块。");
    const category = labeledControl<HTMLSelectElement>(section, "来源归属", "select");
    const sourceType = labeledControl<HTMLSelectElement>(section, "抓取方式", "select");
    if (!category || !sourceType) throw new Error("信息源表单结构不完整。");
    nativeSetSelectValue(category, item.source.sourceCategory);
    nativeSetSelectValue(sourceType, item.source.sourceType);
    await nextFrame();
    await nextFrame();
    const name = labeledControl<HTMLInputElement>(section, "来源名称", "input");
    const company = labeledControl<HTMLInputElement>(section, "公司名称", "input");
    const sector = labeledControl<HTMLSelectElement>(section, "所属赛道", "select");
    const region = labeledControl<HTMLSelectElement>(section, "地区", "select");
    const url = section.querySelector<HTMLInputElement>('input[placeholder="https://example.com/"]');
    const keywords = section.querySelector<HTMLInputElement>('input[placeholder^="逗号分隔"]');
    if (!name || !sector || !region || !url || !keywords) {
      throw new Error("信息源推荐所需字段不完整。");
    }
    nativeSetInputValue(name, item.source.name);
    if (company && item.source.company) nativeSetInputValue(company, item.source.company);
    nativeSetSelectValue(sector, item.source.sector);
    nativeSetSelectValue(region, item.source.region);
    nativeSetInputValue(url, item.source.url);
    nativeSetInputValue(keywords, item.source.keywords.join("，"));
    await nextFrame();
    const button = Array.from(section.querySelectorAll<HTMLButtonElement>("button")).find(
      (candidate) => candidate.textContent?.includes("添加信息源并自动同步"),
    );
    if (!button) throw new Error("未找到信息源添加按钮。");
    button.click();
  }

  if (!mounted || !snapshot.sector) return null;
  const listedSection = sectionByTitle(LISTED_TITLE);
  const sourceSection = sectionByTitle(SOURCE_TITLE);
  if (!listedSection || !sourceSection) return null;
  const listedHost = ensureHost(listedSection, "listed");
  const sourceHostElement = ensureHost(sourceSection, "sources");

  return (
    <>
      {createPortal(
        <TrackingAdminRecommendation
          title="推荐上市公司"
          items={listedRecommendations}
          onAdd={addListed}
          onDismiss={(item) =>
            dismissTrackingRecommendation(
              snapshot.sector,
              "listedCompanies",
              item.value,
            )
          }
        />,
        listedHost,
      )}
      {createPortal(
        <TrackingAdminRecommendation
          title="推荐信息源"
          items={sourceRecommendations as (TrackingSourceRecommendation & AdminRecommendationItem)[]}
          onAdd={addSource}
          onDismiss={(item) =>
            dismissTrackingRecommendation(snapshot.sector, "sources", item.value)
          }
        />,
        sourceHostElement,
      )}
    </>
  );
}
