import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";

const INITIAL_CHANNEL_UPDATE_LIMIT = 120;

export function ChannelUpdateDirectory({
  channel,
  layout = "default",
}: {
  channel: ChannelUpdateKey;
  layout?: "default" | "split";
}) {
  const fullDirectory = getChannelUpdateDirectory(channel);
  const directory = {
    ...fullDirectory,
    items: fullDirectory.items.slice(0, INITIAL_CHANNEL_UPDATE_LIMIT),
  };

  return (
    <ChannelUpdateDirectoryClient
      channel={channel}
      directory={directory}
      totalItemCount={fullDirectory.items.length}
      layout={layout}
    />
  );
}
