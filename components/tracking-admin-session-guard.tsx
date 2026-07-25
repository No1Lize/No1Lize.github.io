"use client";

import { useEffect } from "react";

const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";

function nativeSetInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set;
  setter?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

export function TrackingAdminSessionGuard() {
  useEffect(() => {
    let attempted = false;

    const sync = () => {
      const input = document.querySelector<HTMLInputElement>("#github-token");
      if (!input) return;

      const saved = window.sessionStorage.getItem(TOKEN_SESSION_KEY) ?? "";
      const loginButton = Array.from(
        input.parentElement?.querySelectorAll<HTMLButtonElement>("button") ?? [],
      ).find((button) => /登录|重新载入/.test(button.textContent ?? ""));

      if (saved && !input.value) nativeSetInputValue(input, saved);
      if (saved && loginButton?.textContent?.includes("登录") && !attempted) {
        attempted = true;
        requestAnimationFrame(() => loginButton.click());
      }

      const security = input
        .closest("div")
        ?.parentElement?.querySelector<HTMLElement>("p");
      if (security?.textContent?.includes("Token 仅存在当前页面内存中")) {
        security.textContent =
          "Token 仅保存在当前标签页的 sessionStorage 中；关闭标签页或点击退出后清除，不写入仓库或长期 localStorage。";
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
      if (target.textContent?.trim() === "退出") {
        window.sessionStorage.removeItem(TOKEN_SESSION_KEY);
        attempted = false;
      }
    };

    const observer = new MutationObserver(sync);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("input", onInput, true);
    document.addEventListener("click", onClick, true);
    sync();

    return () => {
      observer.disconnect();
      document.removeEventListener("input", onInput, true);
      document.removeEventListener("click", onClick, true);
    };
  }, []);

  return null;
}
