"use client";

import { useEffect, useState } from "react";
import { TrackingAdminConflictGuard } from "@/components/tracking-admin-conflict-guard";
import { TrackingAdminModuleRecommendations } from "@/components/tracking-admin-module-recommendations";
import { TrackingAdminSessionGuard } from "@/components/tracking-admin-session-guard";
import { TrackingCompanyCandidateReview } from "@/components/tracking-company-candidate-review";
import { TrackingCompanyOnboarding } from "@/components/tracking-company-onboarding";
import { TrackingPeopleScopeEnhancer } from "@/components/tracking-people-scope-enhancer";
import { TrackingRecommendationsBridge } from "@/components/tracking-recommendations-bridge";
import { UserTrackingPanel } from "@/components/user-tracking-panel";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
  cloneTrackingConfig,
  normalizeTrackingConfig,
  type UserTrackingConfig,
} from "@/lib/user-tracking";

function decodeBase64(value: string): string {
  const binary = atob(value.replace(/\n/g, ""));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

export function UserTrackingLoader({ initial }: { initial: UserTrackingConfig }) {
  const [config, setConfig] = useState(() => cloneTrackingConfig(initial));
  const [sourceKey, setSourceKey] = useState("build-snapshot");

  useEffect(() => {
    let cancelled = false;

    async function loadLatestConfig() {
      try {
        const url = `https://api.github.com/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}?ref=${TRACKING_BRANCH}&ts=${Date.now()}`;
        const response = await fetch(url, {
          cache: "no-store",
          headers: {
            Accept: "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
          },
        });
        if (!response.ok) throw new Error(`GitHub API returned ${response.status}`);
        const file = (await response.json()) as { content?: string };
        if (!file.content) throw new Error("GitHub API did not return file content");
        const latest = normalizeTrackingConfig(JSON.parse(decodeBase64(file.content)));
        if (cancelled) return;
        setConfig(latest);
        setSourceKey(`github-${Date.now()}`);
      } catch (error) {
        console.error("Unable to load latest tracking config; using build snapshot.", error);
      }
    }

    void loadLatestConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <TrackingAdminConflictGuard />
      <UserTrackingPanel key={sourceKey} initial={config} />
      <TrackingCompanyCandidateReview />
      <TrackingCompanyOnboarding />
      <TrackingPeopleScopeEnhancer />
      <TrackingRecommendationsBridge />
      <TrackingAdminModuleRecommendations />
      <TrackingAdminSessionGuard />
    </>
  );
}
