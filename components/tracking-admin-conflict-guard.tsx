"use client";

import { useEffect } from "react";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";

const CONFIG_PATH = `/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`;
const DISMISSAL_KINDS = [
  "keywords",
  "people",
  "companies",
  "sources",
  "listedCompanies",
] as const;

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit): string {
  if (init?.method) return init.method.toUpperCase();
  return input instanceof Request ? input.method.toUpperCase() : "GET";
}

function requestHeaders(input: RequestInfo | URL, init?: RequestInit): Headers {
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
  return headers;
}

function jsonResponse(original: Response, payload: unknown): Response {
  const headers = new Headers(original.headers);
  headers.set("Content-Type", "application/json; charset=utf-8");
  headers.delete("Content-Length");
  return new Response(JSON.stringify(payload), {
    status: original.status,
    statusText: original.statusText,
    headers,
  });
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

function normalize(value: unknown): string {
  return typeof value === "string"
    ? value.normalize("NFKC").replace(/\s+/g, " ").trim().toLocaleLowerCase("zh-CN")
    : "";
}

function uniqueValues(left: unknown, right: unknown): string[] {
  const values = new Map<string, string>();
  for (const raw of [
    ...(Array.isArray(left) ? left : []),
    ...(Array.isArray(right) ? right : []),
  ]) {
    if (typeof raw !== "string") continue;
    const cleaned = raw.normalize("NFKC").replace(/\s+/g, " ").trim();
    if (cleaned) values.set(normalize(cleaned), cleaned);
  }
  return [...values.values()].slice(0, 300);
}

function mergeDismissals(outgoingContent: string, remoteContent: string): string {
  try {
    const outgoing = JSON.parse(decodeBase64(outgoingContent)) as {
      tracks?: Array<Record<string, unknown>>;
    };
    const remote = JSON.parse(decodeBase64(remoteContent)) as {
      tracks?: Array<Record<string, unknown>>;
    };
    if (!Array.isArray(outgoing.tracks) || !Array.isArray(remote.tracks)) {
      return outgoingContent;
    }

    for (const outgoingTrack of outgoing.tracks) {
      const slug = normalize(outgoingTrack.slug);
      const name = normalize(outgoingTrack.name);
      const remoteTrack = remote.tracks.find((candidate) => {
        const candidateSlug = normalize(candidate.slug);
        const candidateName = normalize(candidate.name);
        return Boolean(
          (slug && candidateSlug === slug) ||
            (name && candidateName === name),
        );
      });
      if (!remoteTrack) continue;

      const remoteIgnored =
        remoteTrack.ignoredRecommendations &&
        typeof remoteTrack.ignoredRecommendations === "object"
          ? (remoteTrack.ignoredRecommendations as Record<string, unknown>)
          : {};
      const outgoingIgnored =
        outgoingTrack.ignoredRecommendations &&
        typeof outgoingTrack.ignoredRecommendations === "object"
          ? ({ ...(outgoingTrack.ignoredRecommendations as Record<string, unknown>) } as Record<
              string,
              unknown
            >)
          : {};

      for (const kind of DISMISSAL_KINDS) {
        const merged = uniqueValues(outgoingIgnored[kind], remoteIgnored[kind]);
        if (merged.length) outgoingIgnored[kind] = merged;
      }
      if (Object.keys(outgoingIgnored).length) {
        outgoingTrack.ignoredRecommendations = outgoingIgnored;
      }
    }

    return encodeBase64(`${JSON.stringify(outgoing, null, 2)}\n`);
  } catch {
    return outgoingContent;
  }
}

export function TrackingAdminConflictGuard() {
  useEffect(() => {
    const originalFetch = window.fetch.bind(window);
    let panelSha = "";

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = requestUrl(input);
      const method = requestMethod(input, init);
      if (!url.includes(CONFIG_PATH) || !["GET", "PUT"].includes(method)) {
        return originalFetch(input, init);
      }

      const headers = requestHeaders(input, init);
      const authenticated = headers.has("Authorization");

      if (method === "GET") {
        const response = await originalFetch(input, init);
        if (!response.ok || !authenticated) return response;

        try {
          const payload = (await response.clone().json()) as Record<string, unknown>;
          const actualSha = typeof payload.sha === "string" ? payload.sha : "";
          if (!panelSha) panelSha = actualSha;
          else if (actualSha && actualSha !== panelSha) payload.sha = panelSha;
          return jsonResponse(response, payload);
        } catch {
          return response;
        }
      }

      let parsedBody: Record<string, unknown>;
      try {
        const rawBody = init?.body;
        if (typeof rawBody !== "string") return originalFetch(input, init);
        parsedBody = JSON.parse(rawBody) as Record<string, unknown>;
      } catch {
        return originalFetch(input, init);
      }

      let lastResponse: Response | null = null;
      for (let attempt = 0; attempt < 3; attempt += 1) {
        const latestUrl = `https://api.github.com${CONFIG_PATH}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`;
        const latestResponse = await originalFetch(latestUrl, {
          cache: "no-store",
          headers,
        });
        if (!latestResponse.ok) return latestResponse;

        const latest = (await latestResponse.json()) as {
          sha?: string;
          content?: string;
        };
        if (!latest.sha) return originalFetch(input, init);

        const nextBody: Record<string, unknown> = {
          ...parsedBody,
          sha: latest.sha,
        };
        if (
          typeof parsedBody.content === "string" &&
          typeof latest.content === "string"
        ) {
          nextBody.content = mergeDismissals(parsedBody.content, latest.content);
        }

        const response = await originalFetch(input, {
          ...init,
          body: JSON.stringify(nextBody),
        });
        lastResponse = response;

        if (response.ok) {
          try {
            const payload = (await response.clone().json()) as {
              content?: { sha?: string };
            };
            panelSha = payload.content?.sha ?? latest.sha;
          } catch {
            panelSha = latest.sha;
          }
          return response;
        }

        if (response.status !== 409 || attempt >= 2) return response;
        await new Promise<void>((resolve) =>
          window.setTimeout(resolve, 160 * (attempt + 1)),
        );
      }

      return lastResponse ?? originalFetch(input, init);
    };

    return () => {
      window.fetch = originalFetch;
    };
  }, []);

  return null;
}
