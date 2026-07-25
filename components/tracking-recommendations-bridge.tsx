"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  TrackingRecommendations,
  type AnyTrackingRecommendation,
  type RecommendationType,
} from "@/components/tracking-recommendations";
import { validateStrictPersonLabel } from "@/lib/strict-person-label";
import {
  DISMISSAL_EVENT,
  dismissTrackingRecommendation,
  hydrateTrackingRecommendationDismissals,
  isRecommendationDismissed,
} from "@/lib/tracking-recommendation-dismissal";
import {
  recommendTrackingAdditions,
  type TrackingRecommendationSet,
  type TrackingSourceRecommendation,
} from "@/lib/tracking-recommendations";
import { useArticles } from "@/lib/use-articles";

const LIST_FIELD_META = {
  keywords: { placeholder: "例如：VLA", title: "追踪关键词" },
  people: { placeholder: "例如：SpaceX", title: "关键人物 / 关键账号" },
  companies: { placeholder: "例如：OpenAI", title: "样本公司" },
} as const;

type ListRecommendationType = keyof typeof LIST_FIELD_META;

type PanelSnapshot = {
  sector: string;
  keywords: string[];
  people: string[];
  companies: string[];
  sources: string[];
};

const EMPTY_RECOMMENDATIONS: TrackingRecommendationSet = {
  keywords: [],
  people: [],
  companies: [],
  sources: [],
};

function normalizedKey(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("zh-CN");
}

function sourceHost(value: string): string {
  try {
    return new URL(value).hostname.toLocaleLowerCase("en-US").replace(/^www\./, "");
  } catch {
    return "";
  }
}

function fieldInput(type: ListRecommendationType): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>(
    `input[placeholder^="${LIST_FIELD_META[type].placeholder}"]`,
  );
}

function fieldEditor(type: ListRecommendationType): HTMLElement | null {
  let node: HTMLElement | null = fieldInput(type)?.parentElement ?? null;
  while (node && node !== document.body) {
    const heading = node.querySelector<HTMLElement>("h3");
    if (heading?.textContent?.trim() === LIST_FIELD_META[type].title) return node;
    node = node.parentElement;
  }
  return null;
}

function sourceSection(): HTMLElement | null {
  return (
    Array.from(document.querySelectorAll<HTMLElement>("section")).find(
      (section) => section.querySelector("h2")?.textContent?.trim() === "补充信息源",
    ) ?? null
  );
}

function trackDetailSector(): string {
  const detailLabel = Array.from(
    document.querySelectorAll<HTMLElement>("p"),
  ).find((node) => node.textContent?.trim() === "TRACK DETAIL");
  const section = detailLabel?.closest<HTMLElement>("section");
  return section?.querySelector("h2")?.textContent?.trim() ?? "";
}

function currentSector(): string {
  const activeTabs = Array.from(
    document.querySelectorAll<HTMLButtonElement>('button[data-active="true"]'),
  );
  const active = activeTabs.find((button) => {
    const spans = button.querySelectorAll("span");
    return spans.length >= 2 && /启用|停用/.test(spans[1]?.textContent ?? "");
  });
  return active?.querySelector("span")?.textContent?.trim() || trackDetailSector();
}

function existingValues(type: ListRecommendationType): string[] {
  const editor = fieldEditor(type);
  if (!editor) return [];
  return Array.from(editor.querySelectorAll<HTMLButtonElement>("button"))
    .map((button) => button.textContent?.trim() ?? "")
    .filter((value) => value.endsWith("×"))
    .map((value) => value.replace(/\s*×$/, "").trim())
    .filter(Boolean);
}

function existingSourceUrls(): string[] {
  const section = sourceSection();
  if (!section) return [];
  return Array.from(section.querySelectorAll<HTMLElement>("span"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter((value) => /^https?:\/\//i.test(value));
}

function readSnapshot(): PanelSnapshot {
  return {
    sector: currentSector(),
    keywords: existingValues("keywords"),
    people: existingValues("people"),
    companies: existingValues("companies"),
    sources: existingSourceUrls(),
  };
}

function nativeSetInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function nativeSetSelectValue(select: HTMLSelectElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLSelectElement.prototype,
    "value",
  )?.set;
  setter?.call(select, value);
  select.dispatchEvent(new Event("input", { bubbles: true }));
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function labeledControl<T extends HTMLInputElement | HTMLSelectElement>(
  container: HTMLElement,
  labelText: string,
  selector: string,
): T | null {
  const label = Array.from(container.querySelectorAll<HTMLLabelElement>("label")).find(
    (item) => item.textContent?.trim().startsWith(labelText),
  );
  return label?.querySelector<T>(selector) ?? null;
}

function nextFrame(): Promise<void> {
  return new Promise((resolve) => requestAnimationFrame(() => resolve()));
}

async function waitForCondition(
  condition: () => boolean,
  message: string,
  timeoutMs = 2200,
): Promise<void> {
  const started = performance.now();
  while (performance.now() - started < timeoutMs) {
    if (condition()) return;
    await new Promise<void>((resolve) => window.setTimeout(resolve, 50));
  }
  throw new Error(message);
}

async function addListRecommendation(
  type: ListRecommendationType,
  rawValue: string,
) {
  const input = fieldInput(type);
  if (!input) throw new Error("未找到对应的配置输入框。");

  let value = rawValue;
  if (type === "people") {
    const parsed = validateStrictPersonLabel(rawValue);
    if (!parsed.valid) throw new Error(parsed.message);
    value = parsed.normalized;
  }

  nativeSetInputValue(input, value);
  await nextFrame();

  const button = input.parentElement?.querySelector<HTMLButtonElement>("button");
  if (!button || button.disabled) {
    throw new Error("当前推荐未通过输入校验，未执行添加。");
  }
  button.click();

  const expected = normalizedKey(value);
  await waitForCondition(
    () => existingValues(type).some((entry) => normalizedKey(entry) === expected),
    "原管理面板未确认新增条目，请手动重试。",
  );
}

function isSourceRecommendation(
  item: AnyTrackingRecommendation,
): item is TrackingSourceRecommendation {
  return "source" in item;
}

async function addSourceRecommendation(item: TrackingSourceRecommendation) {
  const section = sourceSection();
  if (!section) throw new Error("未找到补充信息源表单。");

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
  const keywords = section.querySelector<HTMLInputElement>(
    'input[placeholder^="逗号分隔"]',
  );

  if (!name || !sector || !region || !url || !keywords) {
    throw new Error("未找到信息源推荐所需的全部字段。");
  }

  nativeSetInputValue(name, item.source.name);
  if (company && item.source.company) {
    nativeSetInputValue(company, item.source.company);
  }
  nativeSetSelectValue(sector, item.source.sector);
  nativeSetSelectValue(region, item.source.region);
  nativeSetInputValue(url, item.source.url);
  nativeSetInputValue(keywords, item.source.keywords.join("，"));
  await nextFrame();

  const button = Array.from(section.querySelectorAll<HTMLButtonElement>("button")).find(
    (candidate) => candidate.textContent?.includes("添加信息源并自动同步"),
  );
  if (!button || button.disabled) {
    throw new Error("推荐信息源未通过表单校验，未执行添加。");
  }
  button.click();

  const expectedHost = sourceHost(item.source.url);
  await waitForCondition(
    () => existingSourceUrls().some((value) => sourceHost(value) === expectedHost),
    "原管理面板未确认新增信息源，请手动重试。",
  );
}

async function addThroughExistingEditor(
  type: RecommendationType,
  item: AnyTrackingRecommendation,
) {
  if (type === "sources") {
    if (!isSourceRecommendation(item)) throw new Error("信息源推荐数据不完整。");
    await addSourceRecommendation(item);
    return;
  }
  await addListRecommendation(type, item.value);
}

function filterDismissed(
  recommendations: TrackingRecommendationSet,
  sector: string,
): TrackingRecommendationSet {
  return {
    keywords: recommendations.keywords.filter(
      (item) => !isRecommendationDismissed(sector, "keywords", item.value),
    ),
    people: recommendations.people.filter(
      (item) => !isRecommendationDismissed(sector, "people", item.value),
    ),
    companies: recommendations.companies.filter(
      (item) => !isRecommendationDismissed(sector, "companies", item.value),
    ),
    sources: recommendations.sources.filter(
      (item) => !isRecommendationDismissed(sector, "sources", item.value),
    ),
  };
}

export function TrackingRecommendationsBridge() {
  const { articles } = useArticles();
  const [mounted, setMounted] = useState(false);
  const [dismissalVersion, setDismissalVersion] = useState(0);
  const [snapshot, setSnapshot] = useState<PanelSnapshot>({
    sector: "",
    keywords: [],
    people: [],
    companies: [],
    sources: [],
  });

  useEffect(() => {
    setMounted(true);
    let frame = 0;
    let previous = "";

    const refresh = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const next = readSnapshot();
        const serialized = JSON.stringify(next);
        if (serialized !== previous) {
          previous = serialized;
          setSnapshot(next);
        }
      });
    };
    const refreshDismissals = () => setDismissalVersion((value) => value + 1);

    const observer = new MutationObserver(refresh);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-active", "disabled"],
    });
    document.addEventListener("input", refresh, true);
    window.addEventListener(DISMISSAL_EVENT, refreshDismissals);
    void hydrateTrackingRecommendationDismissals();
    refresh();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("input", refresh, true);
      window.removeEventListener(DISMISSAL_EVENT, refreshDismissals);
    };
  }, []);

  const recommendations = useMemo(() => {
    if (!snapshot.sector) return EMPTY_RECOMMENDATIONS;
    const generated = recommendTrackingAdditions(articles, snapshot.sector, {
      keywords: snapshot.keywords,
      people: snapshot.people,
      companies: snapshot.companies,
      sources: snapshot.sources,
    });
    return filterDismissed(generated, snapshot.sector);
  }, [articles, dismissalVersion, snapshot]);

  if (!mounted || !snapshot.sector) return null;

  const sourceTarget = sourceSection();
  const dismiss = (type: RecommendationType, item: AnyTrackingRecommendation) =>
    dismissTrackingRecommendation(snapshot.sector, type, item.value);

  return (
    <>
      {(Object.keys(LIST_FIELD_META) as ListRecommendationType[]).map((type) => {
        const target = fieldEditor(type);
        if (!target) return null;
        return createPortal(
          <TrackingRecommendations
            key={`${snapshot.sector}-${type}`}
            recommendations={recommendations}
            onlyType={type}
            sector={snapshot.sector}
            onAdd={addThroughExistingEditor}
            onDismiss={dismiss}
          />,
          target,
        );
      })}
      {sourceTarget
        ? createPortal(
            <TrackingRecommendations
              key={`${snapshot.sector}-sources`}
              recommendations={recommendations}
              onlyType="sources"
              sector={snapshot.sector}
              onAdd={addThroughExistingEditor}
              onDismiss={dismiss}
            />,
            sourceTarget,
          )
        : null}
    </>
  );
}
