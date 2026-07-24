"use client";

import { useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { snapshotDate } from "@/lib/intelligence-data";

const statusSchema = z.object({
  status: z.string(),
  database: z.string(),
  snapshot_updated_at: z.string().nullable(),
});

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL;

async function fetchStatus() {
  if (!apiBase) throw new Error("API is not configured");
  const response = await fetch(`${apiBase.replace(/\/$/, "")}/api/v1/status`);
  if (!response.ok) throw new Error(`API status ${response.status}`);
  return statusSchema.parse(await response.json());
}

export function LiveStatus() {
  const status = useQuery({
    queryKey: ["public-api-status"],
    queryFn: fetchStatus,
    enabled: Boolean(apiBase),
  });
  const online = status.data?.status === "ok";
  const label = online ? "实时 API" : apiBase && status.isError ? "API 延迟 · 使用快照" : "公开快照";
  return <span className="updated" title={status.error instanceof Error ? status.error.message : undefined}><i className={online ? "" : "muted-dot"} /> {label} {snapshotDate}</span>;
}
