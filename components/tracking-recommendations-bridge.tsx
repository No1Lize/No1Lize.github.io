"use client";

import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import {
  TrackingRecommendations,
  type RecommendationType,
} from "@/components/tracking-recommendations";
import { validateStrictPersonLabel } from "@/lib/strict-person-label";
import {
  recommendTrackingAdditions,
  type TrackingRecommendationSet,
} from "@/lib/tracking-recommendations";
import { useArticles } from "@/lib/use-articles";

const FIELD_META: Record<RecommendationType, { placeholder: string; title: string }> = {
  keywords: { placeholder: "例如：VLA", title: "追踪关键词" },
  people: { placeholder: "例如：SpaceX", title: "关键人物 / 关键账号" },
  companies: { placeholder: "例如：OpenAI", title: "样本公司" },
};

type PanelSnapshot = {
  sector: string;
  keywords: string[];
  people: string[];
  companies: string[];
};

const EMPTY_RECOMMENDATIONS: TrackingRecommendationSet = {
  keywords: [],
  people: [],
  companies: [],
};

function fieldInput(type: RecommendationType): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>(
    `input[placeholder^="${FIELD_META[type].placeholder}"]`,
  );
}

function fieldEditor(type: RecommendationType): HTMLElement | null {
  let node: HTMLElement | null = fieldInput(type)?.parentElement ?? null;
  while (node && node !== document.body) {
    const heading = node.querySelector<HTMLElement>("h3");
    if (heading?.textContent?.trim() === FIELD_META[type].title) return node;
    node = node.parentElement;
  }
  return null;
}

function currentSector(): string {
  const activeTabs = Array.from(
    document.querySelectorAll<HTMLButtonElement>('button[data-active="true"]'),
  );
  const active = activeTabs.find((button) => {
    const spans = button.querySelectorAll("span");
    return spans.length >= 2 && /启用|停用/.test(spans[1]?.textContent ?? "");
  });
  return active?.querySelector("span")?.textContent?.trim() ?? "";
}

function existingValues(type: RecommendationType): string[] {
  const editor = fieldEditor(type);
  if (!editor) return [];
  return Array.from(editor.querySelectorAll<HTMLButtonElement>("button"))
    .map((button) => button.textContent?.trim() ?? "")
    .filter((value) => value.endsWith("×"))
    .map((value) => value.replace(/\s*×$/, "").trim())
    .filter(Boolean);
}

function readSnapshot(): PanelSnapshot {
  return {
    sector: currentSector(),
    keywords: existingValues("keywords"),
    people: existingValues("people"),
    companies: existingValues("companies"),
  };
}

function nativeSetValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(
    HTMLInputElement.prototype,
    "value",
  )?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

async function addThroughExistingEditor(type: RecommendationType, rawValue: string) {
  const input = fieldInput(type);
  if (!input) throw new Error("未找到对应的配置输入框。");

  let value = rawValue;
  if (type === "people") {
    const parsed = validateStrictPersonLabel(rawValue);
    if (!parsed.valid) throw new Error(parsed.message);
    value = parsed.normalized;
  }

  nativeSetValue(input, value);
  await new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

  const button = input.parentElement?.querySelector<HTMLButtonElement>("button");
  if (!button || button.disabled) {
    throw new Error("当前推荐未通过输入校验，未执行添加。");
  }
  button.click();
}

export function TrackingRecommendationsBridge() {
  const { articles } = useArticles();
  const [mounted, setMounted] = useState(false);
  const [snapshot, setSnapshot] = useState<PanelSnapshot>({
    sector: "",
    keywords: [],
    people: [],
    companies: [],
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

    const observer = new MutationObserver(refresh);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["data-active", "disabled"],
    });
    document.addEventListener("input", refresh, true);
    refresh();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("input", refresh, true);
    };
  }, []);

  const recommendations = useMemo(
    () =>
      snapshot.sector
        ? recommendTrackingAdditions(articles, snapshot.sector, {
            keywords: snapshot.keywords,
            people: snapshot.people,
            companies: snapshot.companies,
          })
        : EMPTY_RECOMMENDATIONS,
    [articles, snapshot],
  );

  if (!mounted || !snapshot.sector) return null;

  return (
    <>
      {(Object.keys(FIELD_META) as RecommendationType[]).map((type) => {
        const target = fieldEditor(type);
        if (!target) return null;
        return createPortal(
          <TrackingRecommendations
            key={`${snapshot.sector}-${type}`}
            recommendations={recommendations}
            onlyType={type}
            onAdd={addThroughExistingEditor}
          />,
          target,
        );
      })}
    </>
  );
}
