import rawArticles from "@/public/data/articles.json";
import rawPeople from "@/public/data/people.json";
import rawResearchReports from "@/public/data/research_reports.json";
import { getChannelDocumentUpdateItems } from "@/lib/channel-documents";
import { resolveArticleCompanyEntities } from "@/lib/company-entity-registry";
import {
  normalizeChannelUpdateDate,
  type ChannelUpdateDatePrecision,
} from "@/lib/channel-update-date";
import { resolveArticleInstitutionEntities } from "@/lib/institution-entity-registry";
import { trackedSectors } from "@/lib/tracked-sectors";

export type ChannelUpdateKey =
  | "technology"
  | "companies"
  | "institutions"
  | "reports"
  | "people";

export type SourceEvidenceGrade = "A" | "B" | "C" | "D";

export type ChannelUpdateItem = {
  id: string;
  title: string;
  summary: string;
  href: string;
  source: string;
  label: string;
  context: string;
  date: string;
  dateOriginal: string;
  datePrecision: ChannelUpdateDatePrecision;
  sortAt: string;
  keywords: string[];
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  sourceGrade?: SourceEvidenceGrade;
  sourceGradeLabel?: string;
  sourceVerificationPolicy?: string;
};

export type ChannelUpdateDirectory = {
  title: string;
  description: string;
  generatedAt: string;
  items: ChannelUpdateItem[];
};

type ArticleRecord = {
  id: string;
  title: string;
  summary: string;
  type: string;
  region: string;
  sector: string;
  company?: string;
  companySlug?: string;
  companySlugs?: string[];
  companyMatch?: { slug: string; method: string; confidence: number };
  companyMatches?: { slug: string; method: string; confidence: number }[];
  companyCandidateSlugs?: string[];
  institutions?: string[];
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  publishedAt: string;
  importance?: number;
  firstSeenAt?: string;
  firstSeenEstimated?: boolean;
  lastVerifiedAt?: string;
  lastVerifiedEstimated?: boolean;
  source: {
    name: string;
    url: string;
    platform?: string;
    evidenceGrade?: SourceEvidenceGrade;
    evidenceLabel?: string;
    evidencePolicy?: string;
  };
};

type ArticlePayload = {
  generatedAt: string;
  articles: ArticleRecord[];
};

type ResearchReportRecord = {
  id: string;
  title: string;
  publishedAt: string;
  institution: string;
  reportType: string;
  sector: string;
  summary: string;
  sourceName: string;
  sourcePageUrl?: string;
  originalPdfUrl?: string;
  archivedAt?: string;
};

type ResearchReportPayload = {
  generatedAt: string;
  reports: ResearchReportRecord[];
};

type PersonMaterial = {
  title: string;
  date: string;
  type: string;
  url: string;
  source: string;
};

type PersonRecord = {
  slug: string;
  name: string;
  role: string;
  updatedAt?: string;
  materials?: PersonMaterial[];
};

type PeoplePayload = {
  generatedAt: string;
  people: PersonRecord[];
};

const articlesPayload = rawArticles as ArticlePayload;
const researchReportsPayload = rawResearchReports as ResearchReportPayload;
const peoplePayload = rawPeople as PeoplePayload;

const capitalEventTypes = new Set(["融资", "产业投资", "并购", "IPO"]);
const materialTypeLabels: Record<string, string> = {
  speech: "演讲",
  interview: "采访",
  qa: "公开对话",
  research_paper: "论文",
  authored_work: "著作",
  shareholder_letter: "股东信",
  public_document: "公开材料",
  official_profile: "官方资料",
  biography: "人物资料",
};

const enabledSectorNames = new Set(
  trackedSectors.flatMap((sector) => [sector.name, ...(sector.aliases ?? [])]),
);

function normalize(value: string) {
  return value.toLocaleLowerCase("zh-CN").replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function uniqueKeywords(values: string[]) {
  const seen = new Set<string>();
  return values.filter((value) => {
    const keyword = value.trim();
    const normalized = normalize(keyword);
    if (!normalized || seen.has(normalized)) return false;
    seen.add(normalized);
    return true;
  });
}

function dedupeAndSort(items: ChannelUpdateItem[]) {
  const seen = new Set<string>();
  return items
    .filter((item) => {
      const key = `${item.href.trim().toLocaleLowerCase("en-US")}|${normalize(item.title)}`;
      if (!item.href || !item.title || seen.has(key)) return false;
      seen.add(key);
      return true;
    })
    .sort(
      (left, right) =>
        right.sortAt.localeCompare(left.sortAt) || right.title.localeCompare(left.title, "zh-CN"),
    );
}

function articleToUpdate(
  article: ArticleRecord,
  context: string,
  additionalKeywords: string[] = [],
): ChannelUpdateItem {
  const normalizedDate = normalizeChannelUpdateDate(
    article.publishedAt,
    articlesPayload.generatedAt,
  );
  const gradeKeywords = article.source.evidenceGrade
    ? [`${article.source.evidenceGrade}级来源`]
    : [];
  if (article.source.evidenceGrade === "D") gradeKeywords.push("待交叉验证");

  return {
    id: article.id,
    title: article.title,
    summary: article.summary,
    href: article.source.url,
    source: article.source.platform || article.source.name,
    label: article.type,
    context,
    date: normalizedDate.displayDate,
    dateOriginal: normalizedDate.originalDate,
    datePrecision: normalizedDate.precision,
    sortAt: normalizedDate.sortAt,
    keywords: uniqueKeywords([article.type, ...gradeKeywords, ...additionalKeywords]),
    firstSeenAt: article.firstSeenAt,
    firstSeenEstimated: article.firstSeenEstimated,
    lastVerifiedAt: article.lastVerifiedAt,
    lastVerifiedEstimated: article.lastVerifiedEstimated,
    sourceGrade: article.source.evidenceGrade,
    sourceGradeLabel: article.source.evidenceLabel,
    sourceVerificationPolicy: article.source.evidencePolicy,
  };
}

function technologyDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles
    .filter((article) => enabledSectorNames.has(article.sector))
    .map((article) => articleToUpdate(article, `${article.sector} · ${article.region}`));
  return {
    title: "赛道更新目录",
    description: "当前启用赛道的最新公开事件，仅按记录前的绿色事件标签筛选，并按统一日期排序。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("technology"),
      ...items,
    ]),
  };
}

function companiesDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles.flatMap((article) => {
    const matchedCompanies = resolveArticleCompanyEntities(article);
    if (!matchedCompanies.length) return [];
    const companyNames = matchedCompanies
      .slice(0, 3)
      .map((company) => company.name)
      .join("、");
    return [articleToUpdate(article, `${companyNames} · ${article.sector}`)];
  });
  return {
    title: "公司更新目录",
    description: "与已收录公司直接相关的融资、产品、经营和资本市场更新，仅按绿色事件标签筛选。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("companies"),
      ...items,
    ]),
  };
}

function institutionsDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles.flatMap((article) => {
    const matchedInstitutions = resolveArticleInstitutionEntities(article);
    const institutionNames = uniqueKeywords([
      ...matchedInstitutions.map((institution) => institution.name),
      ...(article.institutions ?? []),
    ]).slice(0, 3);

    if (institutionNames.length) {
      return [
        articleToUpdate(
          article,
          `${institutionNames.join("、")} · ${article.sector}`,
          ["机构动态"],
        ),
      ];
    }

    if (!capitalEventTypes.has(article.type)) return [];
    return [
      articleToUpdate(article, `资本事件 · ${article.sector}`, ["资本事件"]),
    ];
  });
  return {
    title: "机构与资本事件更新目录",
    description:
      "已识别具体机构的记录标记为“机构动态”；未识别机构的融资、并购与 IPO 单独标记为“资本事件”。A/B 级为原始或官方来源，C 级为专业报道，D 级仅作待交叉验证线索。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("institutions"),
      ...items,
    ]),
  };
}

function reportsDirectory(): ChannelUpdateDirectory {
  const items = researchReportsPayload.reports.map((report) => {
    const href = report.originalPdfUrl || report.sourcePageUrl || "";
    const orderingDate = report.archivedAt || report.publishedAt;
    const normalizedDate = normalizeChannelUpdateDate(
      orderingDate,
      researchReportsPayload.generatedAt,
    );
    return {
      id: report.id,
      title: report.title,
      summary: report.summary,
      href,
      source: report.sourceName || report.institution,
      label: report.reportType,
      context: `${report.institution} · ${report.sector}`,
      date: normalizedDate.displayDate,
      dateOriginal: normalizedDate.originalDate,
      datePrecision: normalizedDate.precision,
      sortAt: normalizedDate.sortAt,
      keywords: uniqueKeywords([report.reportType]),
    } satisfies ChannelUpdateItem;
  });
  return {
    title: "研报更新目录",
    description: "新归档的公开研报与 PDF 原文，仅按记录前的绿色报告类型标签筛选。",
    generatedAt: researchReportsPayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("reports"),
      ...items,
    ]),
  };
}

function peopleDirectory(): ChannelUpdateDirectory {
  const items = peoplePayload.people.flatMap((person) =>
    (person.materials ?? []).map((material, index) => {
      const normalizedDate = normalizeChannelUpdateDate(
        material.date,
        peoplePayload.generatedAt,
      );
      const materialLabel = materialTypeLabels[material.type] || "人物材料";
      return {
        id: `${person.slug}-${index}-${normalize(material.title)}`,
        title: material.title,
        summary: `${person.name} · ${person.role}`,
        href: material.url,
        source: material.source,
        label: materialLabel,
        context: person.name,
        date: normalizedDate.displayDate,
        dateOriginal: normalizedDate.originalDate,
        datePrecision: normalizedDate.precision,
        sortAt: normalizedDate.sortAt,
        keywords: uniqueKeywords([materialLabel]),
      } satisfies ChannelUpdateItem;
    }),
  );
  return {
    title: "人物材料更新目录",
    description: "人物演讲、采访、公开对话、论文与著作等材料，仅按记录前的绿色材料类型标签筛选。",
    generatedAt: peoplePayload.generatedAt,
    items: dedupeAndSort([
      ...getChannelDocumentUpdateItems("people"),
      ...items,
    ]),
  };
}

export function getChannelUpdateDirectory(
  channel: ChannelUpdateKey,
): ChannelUpdateDirectory {
  switch (channel) {
    case "technology":
      return technologyDirectory();
    case "companies":
      return companiesDirectory();
    case "institutions":
      return institutionsDirectory();
    case "reports":
      return reportsDirectory();
    case "people":
      return peopleDirectory();
  }
}
