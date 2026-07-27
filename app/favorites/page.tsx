import type { Metadata } from "next";
import { FavoritesPage } from "@/components/favorites-page";

export const metadata: Metadata = {
  title: "收藏",
  description: "集中查看收藏内容，并以收藏信号提高相关关键词与信息源的推荐权重。",
};

export default function FavoriteChannelPage() {
  return (
    <main className="page-shell subpage">
      <FavoritesPage />
    </main>
  );
}
