import { Dashboard } from "@/components/dashboard";
import { HomepageChannelUpdates } from "@/components/homepage-channel-updates";

export default function Home() {
  return (
    <main className="page-shell">
      <Dashboard>
        <HomepageChannelUpdates />
      </Dashboard>
    </main>
  );
}
