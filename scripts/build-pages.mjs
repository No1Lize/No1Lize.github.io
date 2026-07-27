#!/usr/bin/env node
// Runs `next build` with GITHUB_PAGES=true on every platform. The previous
// inline `GITHUB_PAGES=true next build` npm script only works in POSIX shells
// and fails on Windows, where npm executes scripts through cmd.exe.
import { spawnSync } from "node:child_process";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const nextBin = require.resolve("next/dist/bin/next");
const result = spawnSync(process.execPath, [nextBin, "build"], {
  stdio: "inherit",
  env: { ...process.env, GITHUB_PAGES: "true" },
});
process.exit(result.status ?? 1);
