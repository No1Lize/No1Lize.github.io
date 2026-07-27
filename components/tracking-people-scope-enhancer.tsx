"use client";

import { useEffect } from "react";

const PEOPLE_HELP =
  "系统会优先从“样本公司”中识别创始人和核心团队，并收集可核验的公开入口，包括 X、微信、知乎、微博、Bilibili、GitHub、LinkedIn、YouTube、个人博客和媒体专栏。有 X handle 时抓取公开时间线，其他入口作为人物来源参与公开索引搜索。";

export function TrackingPeopleScopeEnhancer() {
  useEffect(() => {
    const applyHelpText = () => {
      const heading = Array.from(document.querySelectorAll("h3")).find(
        (node) => node.textContent?.trim() === "关键人物 / 关键账号",
      );
      const help = heading?.nextElementSibling;
      if (!(help instanceof HTMLElement)) return;
      if (help.textContent?.trim() !== PEOPLE_HELP) {
        help.textContent = PEOPLE_HELP;
      }
    };

    applyHelpText();
    const observer = new MutationObserver(applyHelpText);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
    });
    return () => observer.disconnect();
  }, []);

  return null;
}
