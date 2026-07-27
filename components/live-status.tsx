"use client";

import { useArticles } from "@/lib/use-articles";

export function LiveStatus() {
  const { generatedAt, isLive, error } = useArticles();
  return (
    <a
      className="updated"
      title={error instanceof Error ? error.message : undefined}
      href="https://github.com/No1Lize/No1Lize.github.io/actions/workflows/scheduled-sync.yml"
      target="_blank"
      rel="noreferrer"
    >
      <i className={isLive ? "" : "muted-dot"} />
      {isLive ? "资料已同步" : "资料快照"} {generatedAt.slice(0, 10)}
    </a>
  );
}
