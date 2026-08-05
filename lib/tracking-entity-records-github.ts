import {
  GITHUB_API_ROOT,
  base64ToText,
  githubJson,
  textToBase64,
} from "@/lib/github-commit";
import {
  TRACKING_BRANCH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import {
  TRACKING_ENTITY_RECORDS_PATH,
  normalizeTrackingEntityRecordManifest,
  type TrackingEntityRecordManifest,
} from "@/lib/tracking-entity-records";

export type TrackingEntityRecordRepositoryState = {
  fileSha: string;
  username: string;
  manifest: TrackingEntityRecordManifest;
};

export class TrackingEntityRecordConflictError extends Error {
  constructor(message = "远端研究记录已变化，请重新载入后再保存。") {
    super(message);
    this.name = "TrackingEntityRecordConflictError";
  }
}

export async function fetchTrackingEntityRecordRepositoryState(
  token: string,
): Promise<TrackingEntityRecordRepositoryState> {
  const user = await githubJson<{ login: string }>(`${GITHUB_API_ROOT}/user`, token);
  if (user.login.toLocaleLowerCase("en-US") !== TRACKING_OWNER.toLocaleLowerCase("en-US")) {
    throw new Error(`当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}。`);
  }
  const file = await githubJson<{ sha?: string; content?: string }>(
    `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_ENTITY_RECORDS_PATH}?ref=${TRACKING_BRANCH}`,
    token,
  );
  if (!file.sha || !file.content) {
    throw new Error("GitHub 未返回追踪对象研究记录文件。 ");
  }
  return {
    fileSha: file.sha,
    username: user.login,
    manifest: normalizeTrackingEntityRecordManifest(
      JSON.parse(base64ToText(file.content)),
    ),
  };
}

export async function commitTrackingEntityRecordManifest(
  token: string,
  state: TrackingEntityRecordRepositoryState,
  manifest: TrackingEntityRecordManifest,
  entityName: string,
): Promise<string> {
  try {
    const result = await githubJson<{
      commit?: { sha?: string };
    }>(
      `${GITHUB_API_ROOT}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_ENTITY_RECORDS_PATH}`,
      token,
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: `research: update tracked entity ${entityName}`,
          content: textToBase64(`${JSON.stringify(manifest, null, 2)}\n`),
          sha: state.fileSha,
          branch: TRACKING_BRANCH,
        }),
      },
    );
    if (!result.commit?.sha) throw new Error("GitHub 未返回研究记录提交 SHA。");
    return result.commit.sha;
  } catch (error) {
    const status = (error as Error & { status?: number }).status;
    if (status === 409 || status === 422) {
      throw new TrackingEntityRecordConflictError();
    }
    throw error;
  }
}
