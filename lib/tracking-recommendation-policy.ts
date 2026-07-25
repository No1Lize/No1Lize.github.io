import entitySeedConfig from "../config/tracking_entity_seeds.json";
import {
  recommendTrackingAdditions,
  type TrackingRecommendation,
  type TrackingRecommendationSet,
} from "@/lib/tracking-recommendations";
import type { LiveIntelligenceEvent } from "@/lib/use-articles";

type ExistingTrackingValues = {
  keywords?: string[];
  people?: string[];
  companies?: string[];
  sources?: string[];
};

type EntitySeedConfig = {
  globalTerms: string[];
  sectorTerms: Record<string, string[]>;
};

const seeds = entitySeedConfig as EntitySeedConfig;

const GENERIC_CONCEPTS = new Set([
  "agent",
  "agents",
  "algorithm",
  "architecture",
  "benchmark",
  "chip",
  "compiler",
  "context",
  "dataset",
  "framework",
  "inference",
  "memory",
  "model",
  "models",
  "network",
  "platform",
  "protocol",
  "reasoning",
  "robot",
  "rocket",
  "runtime",
  "satellite",
  "system",
  "training",
  "transformer",
  "推理",
  "训练",
  "模型",
  "系统",
  "框架",
  "协议",
  "算法",
  "芯片",
  "机器人",
  "火箭",
  "卫星",
]);

const ENTITY_SUFFIX =
  /\s(?:Transformer|Model|Network|Protocol|Framework|Benchmark|Dataset|Algorithm|Architecture|Agent|Runtime|Compiler)$/;

function normalize(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim();
}

function key(value: string): string {
  return normalize(value).toLocaleLowerCase("zh-CN");
}

function seedTermsForSector(sector: string): Set<string> {
  return new Set(
    [
      ...seeds.globalTerms,
      ...(seeds.sectorTerms[key(sector)] ?? []),
    ].map(key),
  );
}

function hasNamedEntityShape(value: string): boolean {
  const term = normalize(value);
  if (!term || GENERIC_CONCEPTS.has(key(term))) return false;

  // Acronym/project code: GRPO, MCP, VLA, HBM.
  if (/^[A-Z][A-Z0-9]{2,11}(?:-[A-Z0-9]{1,10})*$/.test(term)) return true;

  // Versioned/model identifiers: GPT-5, Gemini 2.5, Qwen3-32B.
  if (/^[A-Za-z][A-Za-z0-9]*(?:[ ._-][A-Za-z0-9]+)*\d[A-Za-z0-9._-]*$/.test(term)) {
    return true;
  }

  // Hyphenated names must contain an uppercase letter or number, excluding prose phrases.
  if (
    term.includes("-") &&
    /[A-Z0-9]/.test(term) &&
    !/^[a-z]+(?:-[a-z]+)+$/.test(term)
  ) {
    return true;
  }

  // Camel/Pascal product or method name: DeepSeek, TensorRT, AutoGen.
  if (/^[A-Z][A-Za-z0-9]*[a-z][A-Z][A-Za-z0-9]*$/.test(term)) return true;

  // Complete named technical entities: Llama Model, Agent2Agent Protocol.
  if (ENTITY_SUFFIX.test(term)) {
    const prefix = term.replace(ENTITY_SUFFIX, "").trim();
    return (
      prefix.length >= 2 &&
      !GENERIC_CONCEPTS.has(key(prefix)) &&
      (/[A-Z0-9]/.test(prefix) || /[\u3400-\u9fff]{2,}/.test(prefix))
    );
  }

  return false;
}

export function isAllowedDisplayedKeywordRecommendation(
  item: TrackingRecommendation,
): boolean {
  const term = normalize(item.value);
  if (!term || GENERIC_CONCEPTS.has(key(term))) return false;

  // Seeded recommendations have already passed the configured vocabulary gate.
  if (!item.reason.startsWith("动态发现：")) return true;

  // Dynamic recommendations must be named entities, never isolated common nouns.
  return hasNamedEntityShape(term);
}

export function isAllowedKeywordRecommendation(
  item: TrackingRecommendation,
  selectedSector: string,
): boolean {
  const term = normalize(item.value);
  if (!term || GENERIC_CONCEPTS.has(key(term))) return false;

  if (seedTermsForSector(selectedSector).has(key(term))) return true;
  return isAllowedDisplayedKeywordRecommendation(item);
}

export function recommendPolicyCheckedTrackingAdditions(
  articles: LiveIntelligenceEvent[],
  selectedSector: string,
  existing: ExistingTrackingValues = {},
): TrackingRecommendationSet {
  const recommendations = recommendTrackingAdditions(
    articles,
    selectedSector,
    existing,
  );
  return {
    ...recommendations,
    keywords: recommendations.keywords.filter((item) =>
      isAllowedKeywordRecommendation(item, selectedSector),
    ),
  };
}
