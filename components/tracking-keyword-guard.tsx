"use client";

import { useEffect, useState } from "react";
import { validateTrackingKeyword } from "@/lib/user-tracking";

type GuardState = {
  visible: boolean;
  message: string;
  kind: "success" | "warning" | "error";
  top: number;
  left: number;
  width: number;
};

const EMPTY_STATE: GuardState = {
  visible: false,
  message: "",
  kind: "success",
  top: 0,
  left: 0,
  width: 0,
};

const SELECTOR = 'input[placeholder^="例如：VLA"]';

function findKeywordInput(): HTMLInputElement | null {
  return document.querySelector<HTMLInputElement>(SELECTOR);
}

function linkedButton(input: HTMLInputElement): HTMLButtonElement | null {
  return input.parentElement?.querySelector<HTMLButtonElement>("button") ?? null;
}

export function TrackingKeywordGuard() {
  const [state, setState] = useState<GuardState>(EMPTY_STATE);

  useEffect(() => {
    let frame = 0;

    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const input = findKeywordInput();
        if (!input) {
          setState(EMPTY_STATE);
          return;
        }

        const value = input.value.trim();
        const button = linkedButton(input);
        if (!value) {
          input.removeAttribute("aria-invalid");
          if (button?.dataset.keywordGuardDisabled === "true") {
            delete button.dataset.keywordGuardDisabled;
            button.disabled = false;
          }
          setState(EMPTY_STATE);
          return;
        }

        const result = validateTrackingKeyword(value);
        const invalid = !result.valid;
        input.setAttribute("aria-invalid", String(invalid));
        if (button) {
          if (invalid) {
            button.dataset.keywordGuardDisabled = "true";
            button.disabled = true;
          } else if (button.dataset.keywordGuardDisabled === "true") {
            delete button.dataset.keywordGuardDisabled;
            button.disabled = false;
          }
        }

        const rect = input.getBoundingClientRect();
        setState({
          visible: true,
          message:
            result.valid && result.normalized !== value
              ? `将规范化为“${result.normalized}”。${result.message}`
              : result.message,
          kind: result.valid ? (result.level === "warning" ? "warning" : "success") : "error",
          top: rect.bottom + 7,
          left: rect.left,
          width: Math.max(rect.width, 300),
        });
      });
    };

    const onInput = (event: Event) => {
      if (event.target instanceof HTMLInputElement && event.target.matches(SELECTOR)) {
        update();
        queueMicrotask(update);
      }
    };

    const onKeyDown = (event: KeyboardEvent) => {
      if (
        event.key === "Enter" &&
        event.target instanceof HTMLInputElement &&
        event.target.matches(SELECTOR)
      ) {
        const result = validateTrackingKeyword(event.target.value);
        if (!result.valid) {
          event.preventDefault();
          event.stopPropagation();
          update();
        }
      }
    };

    const observer = new MutationObserver(update);
    observer.observe(document.body, { childList: true, subtree: true });
    document.addEventListener("input", onInput, true);
    document.addEventListener("keydown", onKeyDown, true);
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    update();

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      document.removeEventListener("input", onInput, true);
      document.removeEventListener("keydown", onKeyDown, true);
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
      const input = findKeywordInput();
      const button = input ? linkedButton(input) : null;
      if (button?.dataset.keywordGuardDisabled === "true") {
        delete button.dataset.keywordGuardDisabled;
        button.disabled = false;
      }
    };
  }, []);

  if (!state.visible) return null;

  const border =
    state.kind === "error"
      ? "var(--red)"
      : state.kind === "warning"
        ? "var(--orange)"
        : "var(--green)";

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: "fixed",
        zIndex: 1000,
        top: state.top,
        left: state.left,
        width: state.width,
        maxWidth: "calc(100vw - 24px)",
        padding: "8px 11px",
        border: `1px solid ${border}`,
        borderLeftWidth: 3,
        borderRadius: 3,
        background: "var(--surface)",
        color: "var(--text)",
        boxShadow: "var(--shadow)",
        fontSize: 13,
        lineHeight: 1.55,
        pointerEvents: "none",
      }}
    >
      {state.message}
    </div>
  );
}
