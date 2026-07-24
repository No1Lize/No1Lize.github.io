import { UserTrackingPanel } from "@/components/user-tracking-panel";
import { userTrackingConfig } from "@/lib/user-tracking";

export default function TrackingPage() {
  return (
    <main className="page-shell subpage">
      <UserTrackingPanel initial={userTrackingConfig} />
    </main>
  );
}
