import assert from "node:assert/strict";
import test from "node:test";

import {
  isAllowedDisplayedKeywordRecommendation,
  isAllowedKeywordRecommendation,
} from "../lib/tracking-recommendation-policy";
import type { TrackingRecommendation } from "../lib/tracking-recommendations";

function recommendation(
  value: string,
  reason = "动态发现：3 条情报、2 个独立来源",
): TrackingRecommendation {
  return {
    value,
    label: value,
    reason,
    score: 100,
  };
}

test("ordinary technical concepts are never displayed as named entities", () => {
  for (const value of [
    "Agent",
    "Inference",
    "Rocket",
    "Model",
    "Framework",
    "Protocol",
    "推理",
    "训练",
    "模型",
    "火箭",
  ]) {
    assert.equal(
      isAllowedDisplayedKeywordRecommendation(recommendation(value)),
      false,
      `${value} is a concept rather than a named entity`,
    );
  }
});

test("unseen named technical entities remain eligible", () => {
  for (const value of [
    "GRPO",
    "GPT-5",
    "DeepSeek-R1",
    "TensorRT",
    "Agent2Agent Protocol",
  ]) {
    assert.equal(
      isAllowedDisplayedKeywordRecommendation(recommendation(value)),
      true,
      `${value} has a named-entity shape`,
    );
  }
});

test("configured compound seed terms remain eligible", () => {
  assert.equal(
    isAllowedKeywordRecommendation(
      recommendation("AI Agent", "赛道种子配置中的高相关技术实体"),
      "AI / AGI",
    ),
    true,
  );
  assert.equal(
    isAllowedKeywordRecommendation(
      recommendation("推理模型", "赛道种子配置中的高相关技术实体"),
      "AI / AGI",
    ),
    true,
  );
});
