"use client";

import { useMemo, useState } from "react";
import {
  TRACKING_CONFIG_PATH,
  TRACKING_REPOSITORY,
  normalizeTrackingConfig,
  type UserTrackingConfig,
} from "@/lib/user-tracking";

const api = "https://api.github.com";

export function UserTrackingPanel({ initial }: { initial: UserTrackingConfig }) {
  const [config, setConfig] = useState(initial);
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("未连接 GitHub");
  const [newTrack, setNewTrack] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [activeTrack, setActiveTrack] = useState(0);

  const current = config.tracks[activeTrack];
  const canEdit = useMemo(() => Boolean(current), [current]);

  function updateConfig(next: UserTrackingConfig) {
    setConfig(normalizeTrackingConfig(next));
  }

  async function syncGithub() {
    try {
      setMessage("正在读取 GitHub 配置...");
      const headers = { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" };
      const file = await fetch(`${api}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`, { headers }).then((r) => r.json());
      const body = btoa(unescape(encodeURIComponent(JSON.stringify(config, null, 2) + "\n")));
      const result = await fetch(`${api}/repos/${TRACKING_REPOSITORY}/contents/${TRACKING_CONFIG_PATH}`, {
        method: "PUT",
        headers: { ...headers, "Content-Type": "application/json" },
        body: JSON.stringify({
          message: "Update technology tracking configuration",
          content: body,
          sha: file.sha,
          branch: "main",
        }),
      });
      if (!result.ok) throw new Error(await result.text());
      setMessage("已同步 GitHub，等待 Actions 重新爬取");
    } catch (error) {
      setMessage(`同步失败: ${String(error)}`);
    }
  }

  return (
    <section className="panel">
      <h1>科技情报配置管理</h1>
      <p>修改赛道、关键词、人物、样本公司和爬取范围。</p>
      <input placeholder="GitHub Fine-grained Token" type="password" value={token} onChange={(e) => setToken(e.target.value)} />
      <div>
        {config.tracks.map((track, i) => (
          <button key={track.slug} onClick={() => setActiveTrack(i)}>{track.name}</button>
        ))}
      </div>
      {canEdit && <>
        <h2>{current.name}</h2>
        <p>关键词</p>
        {current.keywords.map((keyword) => <button key={keyword} onClick={() => updateConfig({...config, tracks: config.tracks.map((t,i)=>i===activeTrack?{...t,keywords:t.keywords.filter(k=>k!==keyword)}:t)})}>{keyword} ×</button>)}
        <input value={newKeyword} onChange={(e)=>setNewKeyword(e.target.value)} placeholder="新增关键词" />
        <button onClick={()=>{if(!newKeyword)return;updateConfig({...config,tracks:config.tracks.map((t,i)=>i===activeTrack?{...t,keywords:[...t.keywords,newKeyword]}:t)});setNewKeyword("")}}>添加</button>
      </>}
      <div>
        <input value={newTrack} onChange={(e)=>setNewTrack(e.target.value)} placeholder="新增赛道" />
        <button onClick={()=>{if(!newTrack)return;updateConfig({...config,tracks:[...config.tracks,{slug:newTrack,name:newTrack,enabled:true,custom:true,keywords:[],people:[],sampleCompanies:[]}]});setNewTrack("")}}>添加赛道</button>
      </div>
      <button onClick={syncGithub}>同步到 GitHub 后端</button>
      <p>{message}</p>
    </section>
  );
}
