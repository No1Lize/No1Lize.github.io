import { DailyHeadlines } from "@/components/daily-headlines";
import { Dashboard } from "@/components/dashboard";
import { HomepageChannelUpdates } from "@/components/homepage-channel-updates";
import { HomepageFavoriteControls } from "@/components/homepage-favorite-controls";

export default function Home() {
  return (
    <main className="page-shell">
      <Dashboard middle={<DailyHeadlines />}>
        <HomepageChannelUpdates />
      </Dashboard>
      <HomepageFavoriteControls />
    </main>
  );
}
