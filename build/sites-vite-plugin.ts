import { access, cp, mkdir, rm } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";

// Packages the Sites hosting manifest after Vite finishes compiling. GitHub
// Pages and pull-request builds do not receive this runtime-only file.
export function sites(): Plugin {
  let root = process.cwd();

  return {
    name: "sites",
    apply: "build",
    configResolved(config) {
      root = config.root;
    },
    async closeBundle() {
      const outputDirectory = resolve(root, "dist", ".openai");
      const hostingConfig = resolve(root, ".openai", "hosting.json");

      try {
        await access(hostingConfig);
      } catch {
        return;
      }

      await rm(outputDirectory, { recursive: true, force: true });
      await mkdir(outputDirectory, { recursive: true });
      await cp(hostingConfig, resolve(outputDirectory, "hosting.json"));
    },
  };
}
