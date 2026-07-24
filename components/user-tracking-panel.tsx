"use client";

import { useState } from "react";
import {
  TRACKING_BRANCH,
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
  normalizeTrackingConfig,
  slugifyTrack,
  type UserTrackingConfig,
} from "@/lib/user-tracking";

const api = "https://api.github.com";

export function UserTrackingPanel({ initial }: { initial: UserTrackingConfig }) {
  const [config, setConfig] = useState(initial);
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("未连接 GitHub");
  const [active, setActive] = useState(0);
  const [input, setInput] = useState("");

  const track = config.tracks[active];

  function update(next: UserTrackingConfig) {
    setConfig(normalizeTrackingConfig(next));
  }

  function changeList(field: "keywords" | "people" | "sampleCompanies", value: string) {
    if (!track || !value.trim()) return;
    update({
      ...config,
      tracks: config.tracks.map((item, index) =>
        index === active
          ? { ...item, [field]: [...item[field], value.trim()] }
          : item,
      ),
    });
    setInput("");
  }

  function removeItem(field: "keywords" | "people" | "sampleCompanies", value: string) {
    update({
      ...config,
      tracks: config.tracks.map((item, index) =>
        index === active
          ? { ...item, [field]: item[field].filter((x) => x !== value) }
          : item,
      ),
    });
  }

  async function syncGithub() {
    const headers = {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
    };
    try {
      setMessage("同步中...");
      const file = await fetch(
        `${api}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`,
        { headers },
      ).then((r) => r.json());
      const content = btoa(
        unescape(encodeURIComponent(JSON.stringify(config, null, 2) + "\n")),
      );
      const result = await fetch(
        `${api}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`,
        {
          method: "PUT",
          headers: { ...headers, "Content-Type": "application/json" },
          body: JSON.stringify({
            message: "Update user technology tracking config",
            content,
            sha: file.sha,
            branch: TRACKING_BRANCH,
          }),
        },
      );
      if (!result.ok) throw new Error(await result.text());
      setMessage("已提交 GitHub，等待爬虫刷新");
    } catch (error) {
      setMessage(`失败: ${String(error)}`);
    }
  }

  return (
    <section className="panel">
      <h1>新兴科技追踪管理</h1>
      <input
        type="password"
        placeholder="GitHub Fine-grained Token"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <div>
        {config.tracks.map((item, index) => (
          <button key={item.slug} onClick={() => setActive(index)}>
            {item.name}
          </button>
        ))}
      </div>
      {track && (
        <>
          <h2>{track.name}</h2>
          {(["keywords", "people", "sampleCompanies"] as const).map((field) => (
            <div key={field}>
              <h3>{field}</h3>
              {track[field].map((item) => (
                <button key={item} onClick={() => removeItem(field, item)}>
                  {item} ×
                </button>
              ))}
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="添加"
              />
              <button onClick={() => changeList(field, input)}>添加</button>
            </div>
          ))}
          <button
            onClick={() =>
              update({
                ...config,
                tracks: config.tracks.filter((_, index) => index !== active),
              })
            }
          >
            删除当前赛道
          </button>
        </>
      )}
      <button
        onClick={() =>
          update({
            ...config,
            tracks: [
              ...config.tracks,
              {
                slug: slugifyTrack(input),
                name: input,
                enabled: true,
                custom: true,
                keywords: [],
                people: [],
                sampleCompanies: [],
              },
            ],
          })
        }
      >
        添加赛道
      </button>
      <button onClick={syncGithub}>同步到 GitHub</button>
      <p>{message}</p>
    </section>
  );
}
