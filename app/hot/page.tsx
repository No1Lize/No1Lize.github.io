import type { Metadata } from "next";
import { HotPage } from "@/components/hot-page";
import type { ArticlePayload, LiveIntelligenceEvent } from "@/lib/use-articles";
import rawArticles from "@/public/data/articles.json";

export const metadata: Metadata = {
  title: "09 热点",
  description: "按当前浏览器的文章打开、收藏与分享行为生成热点排名。",
};

const HOT_BOOTSTRAP_LIMIT = 240;
const snapshot = rawArticles as unknown as ArticlePayload;
const bootstrapArticles: LiveIntelligenceEvent[] = [...snapshot.articles]
  .sort(
    (left, right) =>
      right.importance - left.importance ||
      right.publishedAt.localeCompare(left.publishedAt) ||
      left.title.localeCompare(right.title, "zh-CN"),
  )
  .slice(0, HOT_BOOTSTRAP_LIMIT);

const initialPayload: ArticlePayload = {
  schemaVersion: snapshot.schemaVersion,
  generatedAt: snapshot.generatedAt,
  articleCount: snapshot.articleCount,
  articles: bootstrapArticles,
  sourceStatus: [],
  qualityGate: snapshot.qualityGate,
  refreshAudit: snapshot.refreshAudit,
};

export default function HotChannelPage() {
  return (
    <main className="page-shell subpage">
      <HotPage initialPayload={initialPayload} />
    </main>
  );
}
