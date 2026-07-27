import { ChannelUpdateDirectoryClient } from "@/components/channel-update-directory-client";
import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "@/lib/channel-updates";

export function ChannelUpdateDirectory({
  channel,
}: {
  channel: ChannelUpdateKey;
}) {
  const directory = getChannelUpdateDirectory(channel);
  return <ChannelUpdateDirectoryClient channel={channel} directory={directory} />;
}
