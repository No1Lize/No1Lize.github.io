import { DailyHeadlines } from "@/components/daily-headlines";
import { Dashboard } from "@/components/dashboard";
import { HomepageChannelUpdates } from "@/components/homepage-channel-updates";

export default function Home() {
  return (
    <main className="page-shell">
      <Dashboard middle={<DailyHeadlines />}>
        <HomepageChannelUpdates />
      </Dashboard>
    </main>
  );
}
