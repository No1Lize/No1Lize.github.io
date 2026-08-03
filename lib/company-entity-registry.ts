import rawRegistry from "@/config/official_company_sources.json";

export type CompanyEntityMatch = {
  slug: string;
  method: string;
  confidence: number;
};

export type CompanyEntity = {
  slug: string;
  name: string;
  aliases: string[];
  domains: string[];
  order: number;
};

export type CompanyEntityArticle = {
  company?: string;
  companySlug?: string;
  companySlugs?: string[];
  companyMatch?: CompanyEntityMatch;
  companyMatches?: CompanyEntityMatch[];
  mentionedCompanies?: string[];
  source?: { url?: string };
};

type RawRegistry = {
  companies?: {
    slug?: string;
    name?: string;
    aliases?: string[];
    homepage?: string;
    newsUrls?: string[];
  }[];
};

const genericCompanyNames = new Set([
  "",
  "科技产业",
  "产业",
  "行业",
  "公司",
  "科技公司",
  "未识别",
]);

export function normalizeCompanyIdentity(value: string | undefined) {
  return String(value ?? "")
    .trim()
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function hostname(value: string | undefined) {
  try {
    const host = new URL(String(value ?? "")).hostname.toLocaleLowerCase("en-US");
    return host.startsWith("www.") ? host.slice(4) : host;
  } catch {
    return "";
  }
}

function unique(values: string[]) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = raw.trim();
    const key = normalizeCompanyIdentity(value);
    if (!value || !key || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
  }
  return result;
}

const registry = rawRegistry as RawRegistry;

export const companyEntities: CompanyEntity[] = (registry.companies ?? [])
  .map((row, order) => {
    const slug = String(row.slug ?? "").trim();
    const name = String(row.name ?? "").trim();
    const aliases = unique([name, ...(row.aliases ?? [])]);
    const domains = unique(
      [row.homepage ?? "", ...(row.newsUrls ?? [])]
        .map((url) => hostname(url))
        .filter(Boolean),
    );
    return { slug, name, aliases, domains, order };
  })
  .filter((entity) => entity.slug && entity.name);

const bySlug = new Map(companyEntities.map((entity) => [entity.slug, entity]));
const byAlias = new Map<string, CompanyEntity[]>();
for (const entity of companyEntities) {
  for (const alias of entity.aliases) {
    const key = normalizeCompanyIdentity(alias);
    byAlias.set(key, [...(byAlias.get(key) ?? []), entity]);
  }
}

function uniqueAliasEntity(value: string | undefined) {
  const entities = byAlias.get(normalizeCompanyIdentity(value)) ?? [];
  return entities.length === 1 ? entities[0] : undefined;
}

function domainMatches(host: string, domain: string) {
  return host === domain || host.endsWith(`.${domain}`);
}

function entitiesForSourceUrl(url: string | undefined) {
  const host = hostname(url);
  if (!host) return [];

  const matches = companyEntities.flatMap((entity) =>
    entity.domains
      .filter((domain) => domainMatches(host, domain))
      .map((domain) => ({ entity, specificity: domain.length })),
  );
  if (!matches.length) return [];

  const maximumSpecificity = Math.max(...matches.map((match) => match.specificity));
  const resolved = new Map<string, CompanyEntity>();
  for (const match of matches) {
    if (match.specificity === maximumSpecificity) {
      resolved.set(match.entity.slug, match.entity);
    }
  }
  return [...resolved.values()].sort((left, right) => left.order - right.order);
}

export function resolveArticleCompanyEntities(article: CompanyEntityArticle) {
  const resolved = new Map<string, CompanyEntity>();
  const add = (entity: CompanyEntity | undefined) => {
    if (entity) resolved.set(entity.slug, entity);
  };

  for (const slug of article.companySlugs ?? []) add(bySlug.get(slug));
  add(bySlug.get(article.companySlug ?? ""));
  for (const entity of entitiesForSourceUrl(article.source?.url)) add(entity);

  if (!genericCompanyNames.has(String(article.company ?? "").trim())) {
    add(uniqueAliasEntity(article.company));
  }
  for (const name of article.mentionedCompanies ?? []) add(uniqueAliasEntity(name));

  const storedMatches = [
    ...(article.companyMatches ?? []),
    ...(article.companyMatch ? [article.companyMatch] : []),
  ];
  for (const match of storedMatches) {
    if (Number(match.confidence) >= 0.9) add(bySlug.get(match.slug));
  }

  return [...resolved.values()].sort((left, right) => left.order - right.order);
}

export function companyEntityBySlug(slug: string) {
  return bySlug.get(slug);
}
