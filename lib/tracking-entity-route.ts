import { people } from "@/lib/catalog-data";
import { companyRegistryEntries } from "@/lib/company-registry";
import { stableTrackingCaptureHash, type TrackingCaptureEntityType } from "@/lib/tracking-capture";
import { slugifyTrack } from "@/lib/user-tracking";

export type TrackingEntityRouteDescriptor = {
  id: string;
  entityType: TrackingCaptureEntityType;
  slug: string;
  name: string;
  aliases: string[];
  formalSlug: string;
  formalHref: string;
  formalLabel: string;
  formalSummary: string;
};

function text(value: unknown, limit = 500) {
  return String(value ?? "").normalize("NFKC").replace(/\s+/gu, " ").trim().slice(0, limit);
}

export function normalizeTrackingEntityIdentity(value: string | undefined) {
  return text(value)
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function unique(values: Iterable<string>) {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = text(raw, 300);
    const key = normalizeTrackingEntityIdentity(value);
    if (!value || !key || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
  }
  return result;
}

const companiesByAlias = new Map<string, typeof companyRegistryEntries>();
for (const company of companyRegistryEntries) {
  for (const alias of unique([
    company.name,
    company.englishName ?? "",
    ...(company.aliases ?? []),
  ])) {
    const key = normalizeTrackingEntityIdentity(alias);
    companiesByAlias.set(key, [...(companiesByAlias.get(key) ?? []), company]);
  }
}

const peopleByAlias = new Map<string, typeof people>();
for (const person of people) {
  for (const alias of unique([person.name, person.englishName])) {
    const key = normalizeTrackingEntityIdentity(alias);
    peopleByAlias.set(key, [...(peopleByAlias.get(key) ?? []), person]);
  }
}

function uniqueCompany(name: string) {
  const matches = companiesByAlias.get(normalizeTrackingEntityIdentity(name)) ?? [];
  return matches.length === 1 ? matches[0] : undefined;
}

function uniquePerson(name: string) {
  const matches = peopleByAlias.get(normalizeTrackingEntityIdentity(name)) ?? [];
  return matches.length === 1 ? matches[0] : undefined;
}

export function trackingEntityRouteDescriptor(
  entityType: TrackingCaptureEntityType,
  rawName: string,
): TrackingEntityRouteDescriptor {
  const name = text(rawName, 240);
  if (entityType === "company") {
    const formal = uniqueCompany(name);
    if (formal) {
      return {
        id: `company:${formal.slug}`,
        entityType,
        slug: formal.slug,
        name: formal.name,
        aliases: unique([formal.name, formal.englishName ?? "", ...(formal.aliases ?? []), name]),
        formalSlug: formal.slug,
        formalHref: `/companies/${formal.slug}`,
        formalLabel: "正式公司档案",
        formalSummary: formal.summary,
      };
    }
  }
  if (entityType === "person") {
    const formal = uniquePerson(name);
    if (formal) {
      return {
        id: `person:${formal.slug}`,
        entityType,
        slug: formal.slug,
        name: formal.name,
        aliases: unique([formal.name, formal.englishName, name]),
        formalSlug: formal.slug,
        formalHref: `/people/${formal.slug}`,
        formalLabel: "正式人物档案",
        formalSummary: formal.summary,
      };
    }
  }
  const identity = normalizeTrackingEntityIdentity(name);
  const id = `${entityType}:${identity}`;
  const base = slugifyTrack(name);
  return {
    id,
    entityType,
    slug: `${base}-${stableTrackingCaptureHash(id).slice(0, 6)}`,
    name,
    aliases: name ? [name] : [],
    formalSlug: "",
    formalHref: "",
    formalLabel: "",
    formalSummary: "",
  };
}

export function trackingEntityResearchHref(
  entityType: TrackingCaptureEntityType,
  name: string,
) {
  const descriptor = trackingEntityRouteDescriptor(entityType, name);
  return `/tracking/entities/${entityType}/${descriptor.slug}`;
}
