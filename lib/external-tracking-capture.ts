import {
  stableTrackingCaptureHash,
  type TrackingCaptureEntityDraft,
  type TrackingCaptureEntityType,
  type TrackingCaptureSource,
} from "@/lib/tracking-capture";
import type { UserTrackingConfig } from "@/lib/user-tracking";

export type ExternalTrackingCapturePrefill = {
  source: TrackingCaptureSource;
  entities: TrackingCaptureEntityDraft[];
  selectedText: string;
  preferredTrackSlugs: string[];
};

const ENTITY_TYPES = new Set<TrackingCaptureEntityType>([
  "company",
  "person",
  "topic",
]);

const LATIN_STOPWORDS = new Set([
  "AI",
  "CEO",
  "CTO",
  "IPO",
  "Inc",
  "LLC",
  "Ltd",
  "News",
  "Reuters",
  "USD",
  "US",
]);

function cleanText(value: unknown, limit = 1_000): string {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/\s+/gu, " ")
    .trim()
    .slice(0, limit);
}

function publicHttpUrl(value: unknown): string {
  const text = cleanText(value, 2_000);
  try {
    const url = new URL(text);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : "";
  } catch {
    return "";
  }
}

function sourceNameForUrl(value: string): string {
  try {
    return new URL(value).hostname.replace(/^www\./iu, "");
  } catch {
    return "外部网页";
  }
}

function unique(values: Iterable<string>, limit = 30): string[] {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const value = cleanText(raw, 240);
    const key = value.toLocaleLowerCase("zh-CN");
    if (!value || seen.has(key)) continue;
    result.push(value);
    seen.add(key);
    if (result.length >= limit) break;
  }
  return result;
}

function splitSelections(value: string): string[] {
  return unique(value.split(/[\n\r、；;|｜]+/u), 12);
}

function inferEntityType(value: string): TrackingCaptureEntityType {
  if (/^人物[:：]/u.test(value) || /@[A-Za-z0-9_]{2,}$/u.test(value)) return "person";
  if (/^(?:技术|主题)[:：]/u.test(value)) return "topic";
  return "company";
}

function normalizeEntityName(
  entityType: TrackingCaptureEntityType,
  value: string,
): string {
  const withoutPrefix = value.replace(/^(?:公司|人物|技术|主题)[:：]\s*/u, "").trim();
  return entityType === "company"
    ? withoutPrefix.replace(/\s*公司$/u, "").trim()
    : withoutPrefix;
}

function parseEntityToken(
  value: string,
  requestedType?: TrackingCaptureEntityType,
): TrackingCaptureEntityDraft | null {
  const clean = cleanText(value, 240);
  if (!clean) return null;
  const explicit = clean.match(/^(company|person|topic)[:：](.+)$/iu);
  const entityType = explicit && ENTITY_TYPES.has(explicit[1].toLowerCase() as TrackingCaptureEntityType)
    ? (explicit[1].toLowerCase() as TrackingCaptureEntityType)
    : requestedType ?? inferEntityType(clean);
  const name = normalizeEntityName(entityType, explicit?.[2] ?? clean);
  if (!name) return null;
  return { entityType, name };
}

function latinTitleCandidates(title: string): TrackingCaptureEntityDraft[] {
  const matches = title.match(/\b[A-Z][A-Za-z0-9.-]{2,}\b/gu) ?? [];
  return unique(matches.filter((value) => !LATIN_STOPWORDS.has(value)), 3).map(
    (name) => ({ entityType: "company" as const, name }),
  );
}

function paramsValues(params: URLSearchParams, key: string): string[] {
  return params
    .getAll(key)
    .flatMap((value) => value.split(/[|｜,，]/u))
    .map((value) => cleanText(value, 240))
    .filter(Boolean);
}

export function parseExternalTrackingCaptureParams(
  params: URLSearchParams,
): ExternalTrackingCapturePrefill {
  const url = publicHttpUrl(params.get("url"));
  const title = cleanText(params.get("title"), 300) || sourceNameForUrl(url);
  const selectedText = cleanText(params.get("selection"), 800);
  const context = cleanText(params.get("context") || params.get("summary"), 1_200);
  const requestedType = ENTITY_TYPES.has(params.get("type") as TrackingCaptureEntityType)
    ? (params.get("type") as TrackingCaptureEntityType)
    : undefined;

  const entityTokens = paramsValues(params, "entity");
  const sourceTokens = entityTokens.length
    ? entityTokens
    : selectedText
      ? splitSelections(selectedText)
      : [];
  const entities = sourceTokens
    .map((value) => parseEntityToken(value, requestedType))
    .filter((value): value is TrackingCaptureEntityDraft => Boolean(value));
  const uniqueEntities = entities.filter(
    (entity, index) =>
      entities.findIndex(
        (candidate) =>
          candidate.entityType === entity.entityType &&
          candidate.name.toLocaleLowerCase("zh-CN") === entity.name.toLocaleLowerCase("zh-CN"),
      ) === index,
  );
  const finalEntities = uniqueEntities.length
    ? uniqueEntities
    : latinTitleCandidates(title);
  const sourceName = cleanText(params.get("source"), 160) || sourceNameForUrl(url);
  const eventType = cleanText(params.get("eventType"), 80) || "外部文章采集";
  const summary = context || (selectedText ? `选中文字：${selectedText}` : "");

  return {
    source: {
      articleId: `external-${stableTrackingCaptureHash(`${title}|${url}`)}`,
      title,
      url,
      summary,
      sourceName,
      channel: "external",
      channelLabel: "外部网页",
      eventType,
    },
    entities: finalEntities,
    selectedText,
    preferredTrackSlugs: unique(paramsValues(params, "track"), 12),
  };
}

function normalizedSearchText(prefill: ExternalTrackingCapturePrefill): string {
  return [
    prefill.source.title,
    prefill.source.summary,
    prefill.selectedText,
    ...prefill.entities.map((entity) => entity.name),
  ]
    .join(" ")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN");
}

export function recommendExternalTrackingCaptureTracks(
  prefill: ExternalTrackingCapturePrefill,
  config: UserTrackingConfig,
): string[] {
  const preferred = prefill.preferredTrackSlugs.filter((slug) =>
    config.tracks.some((track) => track.enabled && track.slug === slug),
  );
  if (preferred.length) return preferred;

  const combined = normalizedSearchText(prefill);
  return config.tracks
    .filter((track) => track.enabled)
    .map((track) => {
      let score = 0;
      const trackName = track.name.toLocaleLowerCase("zh-CN");
      if (trackName.length >= 2 && combined.includes(trackName)) score += 10;
      for (const keyword of track.keywords) {
        const candidate = keyword.normalize("NFKC").toLocaleLowerCase("zh-CN").trim();
        if (candidate.length >= 3 && combined.includes(candidate)) score += 3;
      }
      for (const company of track.sampleCompanies) {
        const candidate = company.normalize("NFKC").toLocaleLowerCase("zh-CN").trim();
        if (candidate.length >= 3 && combined.includes(candidate)) score += 6;
      }
      for (const person of track.people) {
        const candidate = person.normalize("NFKC").toLocaleLowerCase("zh-CN").trim();
        if (candidate.length >= 3 && combined.includes(candidate)) score += 4;
      }
      return { slug: track.slug, score };
    })
    .filter((row) => row.score > 0)
    .sort((left, right) => right.score - left.score || left.slug.localeCompare(right.slug))
    .slice(0, 3)
    .map((row) => row.slug);
}

export function externalTrackingCaptureBookmarklet(
  captureUrl = "https://vciq.github.io/tracking/capture/",
): string {
  const target = JSON.stringify(captureUrl);
  return `javascript:(()=>{const s=(window.getSelection?.().toString()||'').trim();const u=new URL(${target});u.searchParams.set('url',location.href);u.searchParams.set('title',document.title);if(s)u.searchParams.set('selection',s);window.open(u.toString(),'_blank','noopener,noreferrer');})();`;
}
