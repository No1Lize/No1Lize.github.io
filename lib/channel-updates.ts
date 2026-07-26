import rawArticles from "@/public/data/articles.json";
import rawPeople from "@/public/data/people.json";
import rawResearchReports from "@/public/data/research_reports.json";
import { companies, institutionCatalog } from "@/lib/catalog-data";
import { trackedSectors } from "@/lib/tracked-sectors";

export type ChannelUpdateKey =
  | "technology"
  | "companies"
  | "institutions"
  | "reports"
  | "people";

export type ChannelUpdateItem = {
  id: string;
  title: string;
  summary: string;
  href: string;
  source: string;
  label: string;
  context: string;
  date: string;
  sortAt: string;
  keywords: string[];
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
  institutions?: string[];
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  publishedAt: string;
  importance?: number;
  source: {
    name: string;
    url: string;
    platform?: string;
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

const genericCompanyNames = new Set(["", "科技产业", "产业", "行业", "公司", "科技公司"]);
const capitalEventTypes = new Set(["融资", "产业投资", "并购", "IPO"]);
const materialTypeLabels: Record<string, string> = {
  speech: "演讲",
  interview: "采访",
  qa: "公开对话",
  research_paper: "论文",
  authored_work: "著作",
  shareholder_letter: "股东信",
  public_document: "公开材料",
};

const enabledSectorNames = new Set(
  trackedSectors.flatMap((sector) => [sector.name, ...(sector.aliases ?? [])]),
);

const companyTerms = companies.flatMap((company) =>
  [company.name, company.englishName]
    .filter((value): value is string => Boolean(value))
    .map((value) => ({ value, normalized: normalize(value) })),
);

const institutionTerms = institutionCatalog.flatMap((institution) =>
  [institution.name, institution.englishName]
    .filter((value): value is string => Boolean(value))
    .map((value) => ({ value, normalized: normalize(value) })),
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

function searchableArticleText(article: ArticleRecord) {
  return normalize(
    [
      article.title,
      article.summary,
      article.company ?? "",
      ...(article.institutions ?? []),
      ...(article.mentionedCompanies ?? []),
      ...(article.mentionedPeople ?? []),
    ].join(" "),
  );
}

function firstMatchedTerm(
  article: ArticleRecord,
  terms: { value: string; normalized: string }[],
) {
  const haystack = searchableArticleText(article);
  return terms.find((term) => term.normalized.length >= 2 && haystack.includes(term.normalized))
    ?.value;
}

function isIsoDate(value: string) {
  return /^\d{4}-\d{2}-\d{2}/u.test(value);
}

function safeDate(value: string | undefined, fallback: string) {
  return value && isIsoDate(value) ? value.slice(0, 10) : fallback.slice(0, 10);
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
        right.sortAt.localeCompare(left.sortAt) || right.date.localeCompare(left.date),
    );
}

function articleToUpdate(
  article: ArticleRecord,
  context: string,
  keywords: string[],
): ChannelUpdateItem {
  return {
    id: article.id,
    title: article.title,
    summary: article.summary,
    href: article.source.url,
    source: article.source.platform || article.source.name,
    label: article.type,
    context,
    date: article.publishedAt,
    sortAt: article.publishedAt,
    keywords: uniqueKeywords([
      article.type,
      article.sector,
      article.region,
      ...keywords,
    ]),
  };
}

function technologyDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles
    .filter((article) => enabledSectorNames.has(article.sector))
    .map((article) =>
      articleToUpdate(article, `${article.sector} · ${article.region}`, [article.sector]),
    );
  return {
    title: "赛道更新目录",
    description: "当前启用赛道的最新公开事件，可按赛道、事件类型和地区关键词筛选，并按时间排序。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort(items),
  };
}

function companiesDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles.flatMap((article) => {
    const matchedCompany = firstMatchedTerm(article, companyTerms);
    const explicitCompany =
      article.company && !genericCompanyNames.has(article.company) ? article.company : "";
    const mentionedCompany = article.mentionedCompanies?.[0] ?? "";
    if (!article.companySlug && !matchedCompany && !explicitCompany && !mentionedCompany) return [];
    const companyName = explicitCompany || mentionedCompany || matchedCompany || "公司动态";
    return [
      articleToUpdate(article, `${companyName} · ${article.sector}`, [
        companyName,
        article.sector,
      ]),
    ];
  });
  return {
    title: "公司更新目录",
    description: "与已收录公司直接相关的融资、产品、经营和资本市场更新，可按公司、赛道和事件关键词筛选。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort(items),
  };
}

function institutionsDirectory(): ChannelUpdateDirectory {
  const items = articlesPayload.articles.flatMap((article) => {
    const matchedInstitution = firstMatchedTerm(article, institutionTerms);
    const explicitInstitution = article.institutions?.[0] ?? "";
    if (!matchedInstitution && !explicitInstitution && !capitalEventTypes.has(article.type)) return [];
    const institution = explicitInstitution || matchedInstitution || "资本动态";
    return [
      articleToUpdate(article, `${institution} · ${article.sector}`, [
        institution,
        article.sector,
      ]),
    ];
  });
  return {
    title: "资本与机构更新目录",
    description: "投资机构、融资、并购与 IPO 相关公开进展，可按机构、赛道和事件关键词筛选。",
    generatedAt: articlesPayload.generatedAt,
    items: dedupeAndSort(items),
  };
}

function reportsDirectory(): ChannelUpdateDirectory {
  const items = researchReportsPayload.reports.map((report) => {
    const href = report.originalPdfUrl || report.sourcePageUrl || "";
    const sortAt = safeDate(report.archivedAt, report.publishedAt);
    return {
      id: report.id,
      title: report.title,
      summary: report.summary,
      href,
      source: report.sourceName || report.institution,
      label: report.reportType,
      context: `${report.institution} · ${report.sector}`,
      date: report.publishedAt,
      sortAt,
      keywords: uniqueKeywords([report.reportType, report.sector, report.institution]),
    } satisfies ChannelUpdateItem;
  });
  return {
    title: "研报更新目录",
    description: "新归档的公开研报与 PDF 原文，可按报告类型、赛道和研究机构关键词筛选。",
    generatedAt: researchReportsPayload.generatedAt,
    items: dedupeAndSort(items),
  };
}

function peopleDirectory(): ChannelUpdateDirectory {
  const items = peoplePayload.people.flatMap((person) =>
    (person.materials ?? []).map((material, index) => {
      const fallback = person.updatedAt || peoplePayload.generatedAt;
      const sortAt = safeDate(material.date, fallback);
      const materialLabel = materialTypeLabels[material.type] || "人物材料";
      return {
        id: `${person.slug}-${index}-${normalize(material.title)}`,
        title: material.title,
        summary: `${person.name} · ${person.role}`,
        href: material.url,
        source: material.source,
        label: materialLabel,
        context: person.name,
        date: material.date || fallback.slice(0, 10),
        sortAt,
        keywords: uniqueKeywords([person.name, materialLabel]),
      } satisfies ChannelUpdateItem;
    }),
  );
  return {
    title: "人物材料更新目录",
    description: "人物演讲、采访、公开对话、论文与著作等材料，可按人物和材料类型关键词筛选。",
    generatedAt: peoplePayload.generatedAt,
    items: dedupeAndSort(items),
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
