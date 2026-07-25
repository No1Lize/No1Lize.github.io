"use client";

import { useEffect } from "react";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";

const CONFIG_PATH = `/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`;

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

        const latest = (await latestResponse.json()) as { sha?: string };
        if (!latest.sha) return originalFetch(input, init);

        const response = await originalFetch(input, {
          ...init,
          body: JSON.stringify({ ...parsedBody, sha: latest.sha }),
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
