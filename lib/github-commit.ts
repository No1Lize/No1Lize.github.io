import { TRACKING_BRANCH, TRACKING_REPOSITORY } from "@/lib/user-tracking";

export const GITHUB_API_ROOT = "https://api.github.com";

export async function githubJson<T>(
  url: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      ...(init?.headers ?? {}),
    },
  });
  const text = await response.text();
  const payload = text ? (JSON.parse(text) as Record<string, unknown>) : {};
  if (!response.ok) {
    const message =
      typeof payload.message === "string" ? payload.message : text;
    const error = new Error(
      `${response.status} ${message || "GitHub API 请求失败"}`,
    );
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  return payload as T;
}

export function bytesToBase64(bytes: Uint8Array): string {
  let binary = "";
  for (let index = 0; index < bytes.length; index += 8192) {
    binary += String.fromCharCode(
      ...Array.from(bytes.subarray(index, index + 8192)),
    );
  }
  return btoa(binary);
}

export function textToBase64(value: string): string {
  return bytesToBase64(new TextEncoder().encode(value));
}

export function base64ToText(value: string): string {
  const binary = atob(value.replace(/\n/g, ""));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export async function fetchRepoTextFile(
  token: string,
  repoPath: string,
): Promise<{ sha: string; text: string }> {
  const file = await githubJson<{ sha: string; content: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${repoPath}?ref=${TRACKING_BRANCH}`,
    token,
  );
  return { sha: file.sha, text: base64ToText(file.content) };
}

export async function putRepoFile(
  token: string,
  options: {
    repoPath: string;
    base64Content: string;
    message: string;
    sha?: string;
  },
): Promise<{ contentSha: string; commitSha: string }> {
  const result = await githubJson<{
    content?: { sha?: string };
    commit?: { sha?: string };
  }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${options.repoPath}`,
    token,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: options.message,
        content: options.base64Content,
        branch: TRACKING_BRANCH,
        ...(options.sha ? { sha: options.sha } : {}),
      }),
    },
  );
  return {
    contentSha: result.content?.sha ?? "",
    commitSha: result.commit?.sha ?? "",
  };
}
