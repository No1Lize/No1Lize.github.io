"use client";

import { useEffect } from "react";

const COMPANY_PEOPLE_HELP =
  "系统会优先从“样本公司”中识别创始人和核心团队，并收集可核验的公开入口，包括 X、微信、知乎、微博、Bilibili、GitHub、LinkedIn、YouTube、个人博客和媒体专栏。有 X handle 时抓取公开时间线，其他入口作为人物来源参与公开索引搜索。";

const INSTITUTION_PEOPLE_HELP =
  "该赛道直接复用“投资机构”频道中已核验的机构核心团队资料，优先同步创始合伙人、管理合伙人和投资合伙人，并登记准确的机构团队页及可核验公开账号。手动删除的自动条目不会再次加入。";

const INSTITUTION_SAMPLE_HELP =
  "直接引用“投资机构”频道已收集的机构档案和团队资料，并作为该赛道的机构与事件搜索词；仍可手动补充其他机构。";

function activeTrackName(): string {
  const detailIndex = Array.from(document.querySelectorAll("p")).find(
    (node) => node.textContent?.trim() === "TRACK DETAIL",
  );
  const heading = detailIndex?.parentElement?.querySelector("h2");
  return heading?.textContent?.trim() ?? "";
}

export function TrackingPeopleScopeEnhancer() {
  useEffect(() => {
    const applyHelpText = () => {
      const investmentTrack = activeTrackName() === "风险投资";
      const peopleHeading = Array.from(document.querySelectorAll("h3")).find(
        (node) => node.textContent?.trim() === "关键人物 / 关键账号",
      );
      const peopleHelp = peopleHeading?.nextElementSibling;
      const peopleText = investmentTrack ? INSTITUTION_PEOPLE_HELP : COMPANY_PEOPLE_HELP;
      if (peopleHelp instanceof HTMLElement && peopleHelp.textContent?.trim() !== peopleText) {
        peopleHelp.textContent = peopleText;
      }

      const sampleHeading = Array.from(document.querySelectorAll("h3")).find((node) => {
        const text = node.textContent?.trim();
        return text === "样本公司" || text === "样本机构";
      });
      if (!(sampleHeading instanceof HTMLElement)) return;
      sampleHeading.textContent = investmentTrack ? "样本机构" : "样本公司";
      const sampleHelp = sampleHeading.nextElementSibling;
      if (sampleHelp instanceof HTMLElement) {
        const text = investmentTrack
          ? INSTITUTION_SAMPLE_HELP
          : "会进入该赛道的公司与事件搜索词。";
        if (sampleHelp.textContent?.trim() !== text) sampleHelp.textContent = text;
      }
      const editor = sampleHeading.parentElement;
      const input = editor?.querySelector("input");
      if (input instanceof HTMLInputElement) {
        input.placeholder = investmentTrack
          ? "来自投资机构频道自动同步，也可手动补充机构名称"
          : "例如：OpenAI、宇树科技";
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
