export type StarInvestorReviewStatus = "verified" | "needs_review" | "rejected";

export type StarInvestorReviewInput = {
  name: string;
  companyName?: string;
  evidence?: string;
  preIpoShares?: number;
  preIpoOwnershipPct?: number;
  reviewStatus?: StarInvestorReviewStatus;
  reviewReasons?: string[];
};

export type StarInvestorReview = {
  reviewStatus: StarInvestorReviewStatus;
  reviewReasons: string[];
};

export const starInvestorReviewLabels: Record<StarInvestorReviewStatus, string> = {
  verified: "已人工核验",
  needs_review: "待人工核验",
  rejected: "质量门已排除",
};

export const starInvestorReviewReasonLabels: Record<string, string> = {
  "awaiting-human-review": "等待人工核验",
  "generic-legal-form": "名称仅为通用法律形式",
  "narrative-name-fragment": "名称疑似正文句子片段",
  "name-not-in-evidence": "名称与证据摘录不一致",
  "no-holding-fact": "未可靠抽取到持股数或比例",
  "issuer-name": "候选名称疑似上市公司自身",
  "invalid-name": "名称不完整",
};

const genericLegalFormNames = new Set([
  "有限公司",
  "股份有限公司",
  "有限责任公司",
  "管理有限公司",
  "投资管理有限公司",
  "基金管理有限公司",
  "资本管理有限公司",
  "股权投资有限公司",
  "管理合伙企业（有限合伙）",
  "管理合伙企业(有限合伙)",
  "投资管理中心（有限合伙）",
  "投资管理中心(有限合伙)",
  "有限合伙",
  "有限合伙企业",
]);

const narrativePrefixes = [
  "整体变更",
  "事务合伙人为",
  "执行事务合伙人为",
  "伙人暨执行事务合伙人为",
  "普通合伙人为",
  "均为",
  "立群通过",
  "雨持有",
];

const narrativeMarkers = [
  "的董事长",
  "的普通合伙人",
  "的执行事务合伙人",
  "担任",
  "持有公司股票",
  "间接持有",
  "的出资额",
  "为发行人",
];

export function normalizeStarInvestorReviewText(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'"“”‘’_\-/\\&+－—]/gu, "")
    .trim();
}

const genericLegalFormKeys = new Set(
  [...genericLegalFormNames].map(normalizeStarInvestorReviewText),
);

function uniqueReasons(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

export function deriveStarInvestorReview(
  input: StarInvestorReviewInput,
): StarInvestorReview {
  if (input.reviewStatus) {
    return {
      reviewStatus: input.reviewStatus,
      reviewReasons: uniqueReasons(input.reviewReasons ?? []),
    };
  }

  const name = String(input.name || "").normalize("NFKC").replace(/\s+/gu, "").trim();
  const nameKey = normalizeStarInvestorReviewText(name);
  const companyKey = normalizeStarInvestorReviewText(input.companyName ?? "");
  const evidenceKey = normalizeStarInvestorReviewText(input.evidence ?? "");

  if (!nameKey) {
    return { reviewStatus: "rejected", reviewReasons: ["invalid-name"] };
  }

  if (
    companyKey.length >= 3 &&
    nameKey.includes(companyKey) &&
    /(?:股份有限公司|有限责任公司|有限公司)$/u.test(name)
  ) {
    return { reviewStatus: "rejected", reviewReasons: ["issuer-name"] };
  }

  if (genericLegalFormKeys.has(nameKey)) {
    return { reviewStatus: "rejected", reviewReasons: ["generic-legal-form"] };
  }

  if (
    narrativePrefixes.some((prefix) => name.startsWith(prefix)) ||
    narrativeMarkers.some((marker) => name.includes(marker))
  ) {
    return { reviewStatus: "rejected", reviewReasons: ["narrative-name-fragment"] };
  }

  if (/^(管理|投资管理|基金管理|资本管理)[（(]/u.test(name)) {
    return { reviewStatus: "rejected", reviewReasons: ["generic-legal-form"] };
  }

  const reviewReasons: string[] = [];
  if (!evidenceKey || !evidenceKey.includes(nameKey)) {
    reviewReasons.push("name-not-in-evidence");
  }
  if (input.preIpoShares === undefined && input.preIpoOwnershipPct === undefined) {
    reviewReasons.push("no-holding-fact");
  }
  reviewReasons.push("awaiting-human-review");

  return {
    reviewStatus: "needs_review",
    reviewReasons: uniqueReasons(reviewReasons),
  };
}
