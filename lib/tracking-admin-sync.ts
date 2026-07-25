"use client";

function statusElement(): HTMLElement | null {
  const tokenInput = document.querySelector<HTMLInputElement>("#github-token");
  const auth = tokenInput?.parentElement?.parentElement;
  return auth?.querySelector<HTMLElement>('p[aria-live="polite"][data-kind]') ?? null;
}

export function currentAdminStatus(): string {
  return statusElement()?.textContent?.trim() ?? "";
}

export async function waitForAdminSave(
  previousStatus: string,
  timeoutMs = 20_000,
): Promise<void> {
  const started = performance.now();
  let observedProgress = false;

  while (performance.now() - started < timeoutMs) {
    const element = statusElement();
    const text = element?.textContent?.trim() ?? "";
    const kind = element?.dataset.kind ?? "";

    if (/正在(?:自动)?同步|正在验证/.test(text)) observedProgress = true;
    if (kind === "error" && /同步失败|连接已失效|远端配置/.test(text)) {
      throw new Error(text.replace(/^同步失败：?/, "") || "GitHub 同步失败。");
    }
    if (
      kind === "success" &&
      /已自动同步|已同步/.test(text) &&
      (observedProgress || text !== previousStatus)
    ) {
      return;
    }

    await new Promise<void>((resolve) => window.setTimeout(resolve, 80));
  }

  throw new Error("GitHub 同步超时，推荐项尚未确认写入仓库。");
}
