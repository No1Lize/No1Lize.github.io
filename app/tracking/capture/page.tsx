import type { Metadata } from "next";
import { ExternalTrackingCapturePage } from "@/components/external-tracking-capture-page";

export const metadata: Metadata = {
  title: "外部文章采集 | VCIQ",
  description:
    "从外部公开网页选择公司、人物和技术主题，并连同原始文章证据加入 VCIQ 追踪、候选审核和研究时间线。",
};

export default function TrackingCapturePage() {
  return <ExternalTrackingCapturePage />;
}
