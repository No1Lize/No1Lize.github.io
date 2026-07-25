import { TrackingCoveragePanel } from "@/components/tracking-coverage-panel";
import { UserTrackingLoader } from "@/components/user-tracking-loader";
import { userTrackingConfig } from "@/lib/user-tracking";

export default function TrackingPage() {
  return (
    <main className="page-shell subpage">
      <TrackingCoveragePanel />
      <UserTrackingLoader initial={userTrackingConfig} />
    </main>
  );
}
