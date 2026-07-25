import { canonicalTrackingSector } from "@/lib/tracking-sector-policy";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";

export type TrackingDismissalKind =
  | "keywords"
  | "people"
  | "companies"
  | "sources"
  | "listedCompanies";

type IgnoredMap = Partial<Record<TrackingDismissalKind, string[]>>;
type SessionStore = Record<string, IgnoredMap>;

const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
const DISMISSAL_SESSION_KEY = "no1lize:tracking-recommendation-dismissals:v1";
export const DISMISSAL_EVENT = "tracking-recommendation-dismissals-updated";

function normalize(value: string): string {
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("zh-CN");
}

function decodeBase64(value: string): string {
  const binary = atob(value.replace(/\n/g, ""));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function encodeBase64(value: string): string {
  const bytes = new TextEncoder().encode(value);
  let binary = "";
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(...Array.from(bytes.subarray(index, index + 8192)));
  }
  return btoa(binary);
}

function readStore(): SessionStore {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.sessionStorage.getItem(DISMISSAL_SESSION_KEY);
    return raw ? (JSON.parse(raw) as SessionStore) : {};
  } catch {
    return {};
  }
}

function writeStore(store: SessionStore): void {
  window.sessionStorage.setItem(DISMISSAL_SESSION_KEY, JSON.stringify(store));
  window.dispatchEvent(new CustomEvent(DISMISSAL_EVENT));
}

function mergeUnique(left: string[] = [], right: string[] = []): string[] {
  const values = new Map<string, string>();
  for (const value of [...left, ...right]) {
    const cleaned = value.normalize("NFKC").replace(/\s+/g, " ").trim();
    if (cleaned) values.set(normalize(cleaned), cleaned);
  }
  return [...values.values()].slice(0, 300);
}

function trackKey(value: string): string {
  return canonicalTrackingSector(value) || normalize(value);
}

function mergeTrackIntoStore(store: SessionStore, rawTrack: Record<string, unknown>): void {
  const sector = String(rawTrack.name ?? rawTrack.slug ?? "");
  const key = trackKey(sector);
  if (!key) return;
  const rawIgnored =
    rawTrack.ignoredRecommendations && typeof rawTrack.ignoredRecommendations === "object"
      ? (rawTrack.ignoredRecommendations as Record<string, unknown>)
      : {};
  const current = store[key] ?? {};
  for (const kind of ["keywords", "people", "companies", "sources", "listedCompanies"] as const) {
    const values = Array.isArray(rawIgnored[kind])
      ? rawIgnored[kind].filter((item): item is string => typeof item === "string")
      : [];
    current[kind] = mergeUnique(current[kind], values);
  }
  store[key] = current;
}

export function ignoredRecommendationValues(
  sector: string,
  kind: TrackingDismissalKind,
): string[] {
  return readStore()[trackKey(sector)]?.[kind] ?? [];
}

export function isRecommendationDismissed(
  sector: string,
  kind: TrackingDismissalKind,
  value: string,
): boolean {
  const target = normalize(value);
  return ignoredRecommendationValues(sector, kind).some((item) => normalize(item) === target);
}

export async function hydrateTrackingRecommendationDismissals(): Promise<void> {
  if (typeof window === "undefined") return;
  const url = `https://api.github.com/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`;
  const response = await fetch(url, {
    cache: "no-store",
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
    },
  });
  if (!response.ok) return;
  const file = (await response.json()) as { content?: string };
  if (!file.content) return;
  try {
    const config = JSON.parse(decodeBase64(file.content)) as { tracks?: unknown[] };
    const store = readStore();
    for (const track of config.tracks ?? []) {
      if (track && typeof track === "object") {
        mergeTrackIntoStore(store, track as Record<string, unknown>);
      }
    }
    writeStore(store);
  } catch {
    // A malformed remote payload must not break the admin page.
  }
}

export async function dismissTrackingRecommendation(
  sector: string,
  kind: TrackingDismissalKind,
  value: string,
): Promise<void> {
  if (typeof window === "undefined") return;
  const cleanValue = value.normalize("NFKC").replace(/\s+/g, " ").trim();
  if (!cleanValue) return;

  const token = window.sessionStorage.getItem(TOKEN_SESSION_KEY)?.trim() ?? "";
  if (!token) throw new Error("管理员 Token 不可用，忽略状态尚未保存。");

  const key = trackKey(sector);
  const nextStore = readStore();
  const nextCurrent = nextStore[key] ?? {};
  nextCurrent[kind] = mergeUnique(nextCurrent[kind], [cleanValue]);
  nextStore[key] = nextCurrent;

  const fileUrl = `https://api.github.com/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`;
  const headers = {
    Accept: "application/vnd.github+json",
    Authorization: `Bearer ${token}`,
    "X-GitHub-Api-Version": "2022-11-28",
  };

  for (let attempt = 0; attempt < 3; attempt += 1) {
    const latestResponse = await fetch(
      `${fileUrl}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`,
      { cache: "no-store", headers },
    );
    if (!latestResponse.ok) throw new Error(`读取远端配置失败（${latestResponse.status}）。`);
    const latest = (await latestResponse.json()) as { sha?: string; content?: string };
    if (!latest.sha || !latest.content) throw new Error("GitHub 未返回完整配置文件。");

    const config = JSON.parse(decodeBase64(latest.content)) as {
      tracks?: Array<Record<string, unknown>>;
    };
    const tracks = Array.isArray(config.tracks) ? config.tracks : [];
    const target = tracks.find((track) =>
      [String(track.name ?? ""), String(track.slug ?? "")]
        .map(trackKey)
        .includes(key),
    );
    if (!target) throw new Error(`未找到赛道“${sector}”。`);

    const ignored =
      target.ignoredRecommendations && typeof target.ignoredRecommendations === "object"
        ? ({ ...(target.ignoredRecommendations as Record<string, unknown>) } as Record<
            string,
            unknown
          >)
        : {};
    const remoteValues = Array.isArray(ignored[kind])
      ? ignored[kind].filter((item): item is string => typeof item === "string")
      : [];
    ignored[kind] = mergeUnique(remoteValues, [cleanValue]);
    target.ignoredRecommendations = ignored;

    const response = await fetch(fileUrl, {
      method: "PUT",
      headers: { ...headers, "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "config: persist dismissed tracking recommendation",
        content: encodeBase64(`${JSON.stringify(config, null, 2)}\n`),
        sha: latest.sha,
        branch: TRACKING_BRANCH,
      }),
    });
    if (response.ok) {
      writeStore(nextStore);
      return;
    }
    if (response.status !== 409 || attempt === 2) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(
        `保存忽略状态失败（${response.status} ${String((payload as { message?: string }).message ?? "")}）。`,
      );
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, 180 * (attempt + 1)));
  }
}
