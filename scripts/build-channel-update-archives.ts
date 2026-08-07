import { writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

import {
  getChannelUpdateDirectory,
  type ChannelUpdateKey,
} from "../lib/channel-updates";

const ROOT = process.cwd();
const OUTPUT = path.join(ROOT, "public", "data", "channel_update_directories.json");
const channels: ChannelUpdateKey[] = [
  "technology",
  "companies",
  "institutions",
  "reports",
  "people",
];

const directories = Object.fromEntries(
  channels.map((channel) => [channel, getChannelUpdateDirectory(channel)]),
);

const payload = {
  schemaVersion: 1,
  channels: directories,
};

writeFileSync(OUTPUT, `${JSON.stringify(payload)}\n`, "utf8");
console.log(
  `Built channel update archives: ${channels
    .map((channel) => `${channel}=${directories[channel].items.length}`)
    .join(", ")} -> ${path.relative(ROOT, OUTPUT)}`,
);
