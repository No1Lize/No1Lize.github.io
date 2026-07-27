"use client";

import { useEffect } from "react";

const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
const GITHUB_REQUEST_TIMEOUT_MS = 15_000;

function nativeSetInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.href;
  return input.url;
}

function isGithubApiRequest(input: RequestInfo | URL): boolean {
  try {
    return new URL(requestUrl(input), window.location.href).hostname === "api.github.com";
  } catch {
    return false;
  }
}

export function TrackingAdminSessionGuard() {
  useEffect(() => {
    const originalFetch = window.fetch.bind(window);

    const guardedFetch: typeof window.fetch = async (input, init) => {
      if (!isGithubApiRequest(input)) return originalFetch(input, init);

      const controller = new AbortController();
      const upstreamSignal = init?.signal ?? (input instanceof Request ? input.signal : undefined);
      let timedOut = false;

      const abortFromUpstream = () => controller.abort(upstreamSignal?.reason);
      if (upstreamSignal?.aborted) abortFromUpstream();
      else upstreamSignal?.addEventListener("abort", abortFromUpstream, { once: true });

      const timer = window.setTimeout(() => {
        timedOut = true;
        controller.abort();
      }, GITHUB_REQUEST_TIMEOUT_MS);

      try {
        return await originalFetch(input, {
          ...init,
          cache: "no-store",
          signal: controller.signal,
        });
      } catch (error) {
        if (timedOut) {
          throw new Error(
            "GitHub API 请求超过 15 秒未响应。请检查网络、代理或浏览器扩展后重新登录。",
          );
        }
        throw error;
      } finally {
        window.clearTimeout(timer);
        upstreamSignal?.removeEventListener("abort", abortFromUpstream);
      }
    };

    window.fetch = guardedFetch;

    const sync = () => {
      const input = document.querySelector<HTMLInputElement>("#github-token");
      if (!input) return;

      const saved = window.sessionStorage.getItem(TOKEN_SESSION_KEY) ?? "";
      if (saved && !input.value) {
        // Restore the value into React's controlled input, but do not click the
        // login button automatically. Manual login avoids a race between the
        // synthetic input event and the component's token state update.
        nativeSetInputValue(input, saved);
      }

      const security = Array.from(
        input.closest("div")?.parentElement?.querySelectorAll<HTMLElement>("p") ?? [],
      ).find((paragraph) =>
        paragraph.textContent?.includes("Token 仅存在当前页面内存中") ||
        paragraph.textContent?.includes("Token 仅保存在当前标签页"),
      );
      if (security) {
        security.textContent =
          "Token 仅保存在当前标签页的 sessionStorage 中；关闭标签页或点击退出后清除。GitHub API 超过 15 秒无响应时会自动终止请求并恢复登录按钮。";
      }
    };

    const onInput = (event: Event) => {
      const input = event.target;
      if (!(input instanceof HTMLInputElement) || input.id !== "github-token") return;
      const value = input.value.trim();
      if (value) window.sessionStorage.setItem(TOKEN_SESSION_KEY, value);
      else window.sessionStorage.removeItem(TOKEN_SESSION_KEY);
    };

    const onClick = (event: MouseEvent) => {
      const target = event.target;
      if (!(target instanceof HTMLButtonElement)) return;

      const label = target.textContent?.trim() ?? "";
      if (/登录|重新载入/.test(label)) {
        const input = document.querySelector<HTMLInputElement>("#github-token");
        const value = input?.value.trim() ?? "";
        if (value) window.sessionStorage.setItem(TOKEN_SESSION_KEY, value);
      }

      if (label === "退出") {
        window.sessionStorage.removeItem(TOKEN_SESSION_KEY);
      }
    };

    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("input", onInput, true);
    document.addEventListener("click", onClick, true);
    sync();

    return () => {
      if (window.fetch === guardedFetch) window.fetch = originalFetch;
      observer.disconnect();
      document.removeEventListener("input", onInput, true);
      document.removeEventListener("click", onClick, true);
    };
  }, []);

  return null;
}
