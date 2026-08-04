import rawAliasConfig from "@/config/institution_entity_aliases.json";
import {
  institutionDirectory,
  type InstitutionDirectoryEntry,
} from "@/lib/institution-ranking-data";

export type InstitutionEntity = {
  id: string;
  name: string;
  fullName?: string;
  profileSlug?: string;
  aliases: string[];
  domains: string[];
  directoryEntry: InstitutionDirectoryEntry;
  order: number;
};

export type InstitutionEntityArticle = {
  title?: string;
  summary?: string;
  institutions?: string[];
  company?: string;
  mentionedCompanies?: string[];
  mentionedPeople?: string[];
  source?: { url?: string };
};

export type InstitutionEntityMatchMethod =
  | "structured-field"
  | "official-domain"
  | "reviewed-alias-text";

export type InstitutionEntityMatch = {
  entity: InstitutionEntity;
  methods: InstitutionEntityMatchMethod[];
  evidence: string[];
};

type AliasConfig = {
  schemaVersion?: number;
  entities?: Record<string, string[]>;
};

const aliasConfig = rawAliasConfig as AliasConfig;

export function normalizeInstitutionIdentity(value: string | undefined) {
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
    const key = normalizeInstitutionIdentity(value);
    if (!value || !key || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
  }
  return result;
}

function entityId(entry: InstitutionDirectoryEntry) {
  return entry.profileSlug
    ? `profile:${entry.profileSlug}`
    : `institution:${normalizeInstitutionIdentity(entry.name)}`;
}

export const institutionEntities: InstitutionEntity[] = institutionDirectory.map(
  (entry, order) => ({
    id: entityId(entry),
    name: entry.name,
    fullName: entry.fullName,
    profileSlug: entry.profileSlug,
    aliases: unique([
      entry.name,
      entry.fullName ?? "",
      ...(aliasConfig.entities?.[entry.name] ?? []),
    ]),
    domains: unique([hostname(entry.officialUrl)].filter(Boolean)),
    directoryEntry: entry,
    order,
  }),
);

const byId = new Map(institutionEntities.map((entity) => [entity.id, entity]));
const byAlias = new Map<string, InstitutionEntity[]>();
for (const entity of institutionEntities) {
  for (const alias of entity.aliases) {
    const key = normalizeInstitutionIdentity(alias);
    byAlias.set(key, [...(byAlias.get(key) ?? []), entity]);
  }
}

function uniqueAliasEntity(value: string | undefined) {
  const entities = byAlias.get(normalizeInstitutionIdentity(value)) ?? [];
  return entities.length === 1 ? entities[0] : undefined;
}

function domainMatches(host: string, domain: string) {
  return host === domain || host.endsWith(`.${domain}`);
}

function entitiesForSourceUrl(url: string | undefined) {
  const host = hostname(url);
  if (!host) return { host: "", entities: [] as InstitutionEntity[] };

  const matches = institutionEntities.flatMap((entity) =>
    entity.domains
      .filter((domain) => domainMatches(host, domain))
      .map((domain) => ({ entity, specificity: domain.length })),
  );
  if (!matches.length) return { host, entities: [] as InstitutionEntity[] };

  const maximumSpecificity = Math.max(...matches.map((match) => match.specificity));
  const resolved = new Map<string, InstitutionEntity>();
  for (const match of matches) {
    if (match.specificity === maximumSpecificity) {
      resolved.set(match.entity.id, match.entity);
    }
  }
  return {
    host,
    entities: [...resolved.values()].sort((left, right) => left.order - right.order),
  };
}

function searchableArticleText(article: InstitutionEntityArticle) {
  return normalizeInstitutionIdentity(
    [
      article.title ?? "",
      article.summary ?? "",
      article.company ?? "",
      ...(article.institutions ?? []),
      ...(article.mentionedCompanies ?? []),
      ...(article.mentionedPeople ?? []),
    ].join(" "),
  );
}

function aliasEligibleForTextMatch(alias: string) {
  const normalized = normalizeInstitutionIdentity(alias);
  if (!normalized) return false;
  const onlyChinese = /^[\u3400-\u9fff]+$/u.test(normalized);
  return onlyChinese ? normalized.length >= 3 : normalized.length >= 4;
}

const textAliases = [...byAlias.entries()]
  .filter(([, entities]) => entities.length === 1)
  .flatMap(([normalized, entities]) =>
    entities[0].aliases
      .filter(aliasEligibleForTextMatch)
      .filter((alias) => normalizeInstitutionIdentity(alias) === normalized)
      .map((alias) => ({
        normalized,
        entity: entities[0],
        alias,
      })),
  )
  .sort(
    (left, right) =>
      right.normalized.length - left.normalized.length ||
      left.entity.order - right.entity.order,
  );

export function resolveArticleInstitutionEntityMatches(
  article: InstitutionEntityArticle,
): InstitutionEntityMatch[] {
  const resolved = new Map<
    string,
    {
      entity: InstitutionEntity;
      methods: Set<InstitutionEntityMatchMethod>;
      evidence: Set<string>;
    }
  >();
  const add = (
    entity: InstitutionEntity | undefined,
    method: InstitutionEntityMatchMethod,
    evidence: string,
  ) => {
    if (!entity) return;
    const current = resolved.get(entity.id) ?? {
      entity,
      methods: new Set<InstitutionEntityMatchMethod>(),
      evidence: new Set<string>(),
    };
    current.methods.add(method);
    if (evidence.trim()) current.evidence.add(evidence.trim());
    resolved.set(entity.id, current);
  };

  for (const institution of article.institutions ?? []) {
    add(uniqueAliasEntity(institution), "structured-field", institution);
  }

  const sourceMatch = entitiesForSourceUrl(article.source?.url);
  for (const entity of sourceMatch.entities) {
    add(entity, "official-domain", sourceMatch.host);
  }

  const haystack = searchableArticleText(article);
  if (haystack) {
    for (const candidate of textAliases) {
      if (haystack.includes(candidate.normalized)) {
        add(candidate.entity, "reviewed-alias-text", candidate.alias);
      }
      if (resolved.size >= 5) break;
    }
  }

  return [...resolved.values()]
    .sort((left, right) => left.entity.order - right.entity.order)
    .map((match) => ({
      entity: match.entity,
      methods: [...match.methods],
      evidence: [...match.evidence],
    }));
}

export function resolveArticleInstitutionEntities(article: InstitutionEntityArticle) {
  return resolveArticleInstitutionEntityMatches(article).map((match) => match.entity);
}

export function institutionEntityById(id: string) {
  return byId.get(id);
}

export function institutionEntityByName(name: string) {
  return uniqueAliasEntity(name);
}

export const institutionEntityRegistryStats = {
  entities: institutionEntities.length,
  aliases: [...byAlias.keys()].length,
  officialDomains: new Set(institutionEntities.flatMap((entity) => entity.domains)).size,
};
