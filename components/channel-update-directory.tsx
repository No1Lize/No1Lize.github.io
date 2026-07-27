import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";

export function ChannelUpdateDirectory({
  channel,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  layout?: "default" | "split";
}) {
  const directory = getChannelUpdateDirectory(channel);
  return (
    <ChannelUpdateDirectoryClient
      channel={channel}
      directory={directory}
      layout={layout}
    />
  );
}
