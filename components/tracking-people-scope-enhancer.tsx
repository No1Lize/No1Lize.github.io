"use client";

import { useEffect } from "react";
import { institutionDirectoryStats } from "@/lib/institution-ranking-data";

const COMPANY_PEOPLE_HELP =
  "系统会优先从“样本公司”中识别创始人和核心团队，并收集可核验的公开入口，包括 X、微信、知乎、微博、Bilibili、GitHub、LinkedIn、YouTube、个人博客和媒体专栏。有 X handle 时抓取公开时间线，其他入口作为人物来源参与公开索引搜索。";

const INSTITUTION_PEOPLE_HELP =
  "该赛道直接复用“投资机构”频道中已核验的机构核心团队资料，优先同步创始合伙人、管理合伙人和投资合伙人，并登记准确的机构团队页及可核验公开账号。未被机构档案核验的自动人物不会保留，手动删除的自动条目不会再次加入。";

const INSTITUTION_SAMPLE_HELP =
  `直接引用“投资机构”频道完整目录中的全部 ${institutionDirectoryStats.total} 家机构，而不是只引用已建立详细研究档案的少数机构；目录增删会自动同步，仍可手动补充目录外机构。`;

function activeTrackName(): string {
  const detailIndex = Array.from(document.querySelectorAll("p")).find(
    (node) => node.textContent?.trim() === "TRACK DETAIL",
  );
  const heading = detailIndex?.parentElement?.querySelector("h2");
  return heading?.textContent?.trim() ?? "";
}

export function TrackingPeopleScopeEnhancer() {
  useEffect(() => {
    let frame = 0;

    const applyHelpText = () => {
      frame = 0;
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

      const desiredHeading = investmentTrack ? "样本机构" : "样本公司";
      if (sampleHeading.textContent?.trim() !== desiredHeading) {
        sampleHeading.textContent = desiredHeading;
      }

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
        const placeholder = investmentTrack
          ? "完整机构目录自动同步；此处仅补充目录外机构"
          : "例如：OpenAI、宇树科技";
        if (input.placeholder !== placeholder) input.placeholder = placeholder;
      }
    };

    const scheduleApply = () => {
      if (frame) return;
      frame = requestAnimationFrame(applyHelpText);
    };

    applyHelpText();
    const observer = new MutationObserver(scheduleApply);
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["data-active"],
    });
    return () => {
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);

  return null;
}
