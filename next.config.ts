import type { NextConfig } from "next";

const isGitHubPages = process.env.GITHUB_PAGES === "true";

const nextConfig: NextConfig = {
  output: isGitHubPages ? "export" : undefined,
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
