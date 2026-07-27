import { UserTrackingLoader } from "@/components/user-tracking-loader";
import { userTrackingConfig } from "@/lib/user-tracking";

export default function TrackingPage() {
  return (
    <main className="page-shell subpage">
      <UserTrackingLoader initial={userTrackingConfig} />
    </main>
  );
}
