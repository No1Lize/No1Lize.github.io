import type { Metadata } from "next";
import { HotPage } from "@/components/hot-page";

export const metadata: Metadata = {
  title: "09 热点",
  description: "按当前浏览器的文章打开、收藏与分享行为生成热点排名。",
};

export default function HotChannelPage() {
  return (
    <main className="page-shell subpage">
      <HotPage />
    </main>
  );
}
