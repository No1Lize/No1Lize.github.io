"use client";

import { FileText, Trash2, Upload, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CHANNEL_DOCUMENT_MAX_BYTES,
  CHANNEL_DOCUMENTS_PATH,
  buildChannelDocumentPath,
  channelDocumentToUpdateItem,
  channelDocumentTypeLabel,
  createChannelDocumentId,
  detectChannelDocumentFileType,
  normalizeChannelDocuments,
  safeChannelDocumentFileName,
  type ChannelDocumentChannel,
  type ChannelDocumentFileType,
  type ChannelDocumentRecord,
} from "@/lib/channel-documents";
import type { ChannelUpdateItem } from "@/lib/channel-updates";
import {
  extractDocxDocument,
  extractPptxDocument,
} from "@/lib/document-extract";
import { extractPdfDocument } from "@/lib/document-extract-pdf";
import { generateDocumentSummary } from "@/lib/document-summary";
import {
  GITHUB_API_ROOT,
  bytesToBase64,
  fetchRepoTextFile,
  githubJson,
  putRepoFile,
  textToBase64,
} from "@/lib/github-commit";
import {
  TRACKING_BRANCH,
  TRACKING_OWNER,
  TRACKING_REPOSITORY,
} from "@/lib/user-tracking";
import styles from "./channel-document-import.module.css";

const TOKEN_SESSION_KEY = "no1lize:tracking-admin-token";
const ACCEPTED_INPUT =
  ".pdf,.doc,.docx,.ppt,.pptx,.txt,.md,.markdown,.csv,image/*,application/pdf";

type EntryStatus = "parsing" | "ready" | "saving" | "saved" | "error";

type ImportEntry = {
  key: string;
  docId: string;
  fileName: string;
  fileType: ChannelDocumentFileType;
  fileSize: number;
  bytes: Uint8Array | null;
  title: string;
  summary: string;
  pageCount?: number;
  textChars: number;
  status: EntryStatus;
  detail: string;
};

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function defaultTitle(fileName: string): string {
  const withoutExtension = fileName.replace(/\.[a-zA-Z0-9]{1,10}$/, "").trim();
  return (withoutExtension || fileName).slice(0, 120);
}

function fallbackSummary(fileType: ChannelDocumentFileType): string {
  if (fileType === "doc" || fileType === "ppt") {
    return "旧版 Office 二进制格式，未自动提取正文；可在提交前手动补写摘要。";
  }
  if (fileType === "image") return "图片文件，已归档原图。";
  return "已归档文件，未提取到可用正文。";
}

function clipboardFileName(now: Date): string {
  const stamp = now
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+$/, "")
    .replace("T", "-");
  return `剪贴板-${stamp}.md`;
}

export function ChannelDocumentImport({
  channel,
  open,
  incomingFiles,
  onIncomingConsumed,
  onClose,
  onSaved,
}: {
  channel: ChannelDocumentChannel;
  open: boolean;
  incomingFiles: File[] | null;
  onIncomingConsumed: () => void;
  onClose: () => void;
  onSaved: (item: ChannelUpdateItem) => void;
}) {
  const [entries, setEntries] = useState<ImportEntry[]>([]);
  // Shares the /tracking admin session so one login covers both surfaces.
  const [token, setToken] = useState(() =>
    typeof window === "undefined"
      ? ""
      : (window.sessionStorage.getItem(TOKEN_SESSION_KEY) ?? ""),
  );
  const entriesRef = useRef<ImportEntry[]>([]);
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const usernameRef = useRef("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const applyEntries = useCallback(
    (updater: (previous: ImportEntry[]) => ImportEntry[]) => {
      setEntries((previous) => {
        const next = updater(previous);
        entriesRef.current = next;
        return next;
      });
    },
    [],
  );

  const updateEntry = useCallback(
    (key: string, patch: Partial<ImportEntry>) => {
      applyEntries((previous) =>
        previous.map((entry) =>
          entry.key === key ? { ...entry, ...patch } : entry,
        ),
      );
    },
    [applyEntries],
  );

  const ingestFiles = useCallback(
    async (files: File[]) => {
      for (const file of files) {
        const fileType = detectChannelDocumentFileType(file.name, file.type);
        const docId = createChannelDocumentId();
        const base: ImportEntry = {
          key: docId,
          docId,
          fileName: file.name || `文件-${docId}`,
          fileType: fileType ?? "text",
          fileSize: file.size,
          bytes: null,
          title: defaultTitle(file.name || docId),
          summary: "",
          textChars: 0,
          status: "parsing",
          detail: "正在读取文件……",
        };
        if (!fileType) {
          applyEntries((previous) => [
            ...previous,
            {
              ...base,
              status: "error",
              detail: "不支持的文件类型：仅支持 PDF、Word、PPT、文本和图片。",
            },
          ]);
          continue;
        }
        if (file.size > CHANNEL_DOCUMENT_MAX_BYTES) {
          applyEntries((previous) => [
            ...previous,
            {
              ...base,
              status: "error",
              detail: `文件超过 ${sizeLabel(CHANNEL_DOCUMENT_MAX_BYTES)} 上限，无法写入仓库。`,
            },
          ]);
          continue;
        }
        applyEntries((previous) => [...previous, base]);
        try {
          const bytes = new Uint8Array(await file.arrayBuffer());
          let text = "";
          let pageCount: number | undefined;
          let parseNote = "";
          try {
            if (fileType === "pdf") {
              updateEntry(docId, { detail: "正在解析 PDF 正文……" });
              const parsed = await extractPdfDocument(bytes);
              text = parsed.text;
              pageCount = parsed.pageCount;
            } else if (fileType === "docx") {
              updateEntry(docId, { detail: "正在解析 Word 正文……" });
              text = (await extractDocxDocument(bytes)).text;
            } else if (fileType === "pptx") {
              updateEntry(docId, { detail: "正在解析幻灯片文本……" });
              const parsed = await extractPptxDocument(bytes);
              text = parsed.text;
              pageCount = parsed.slideCount;
            } else if (fileType === "text") {
              text = new TextDecoder().decode(bytes);
            }
          } catch (error) {
            parseNote = `正文提取失败：${
              error instanceof Error ? error.message : String(error)
            } 仍可归档原文件。`;
          }
          const trimmed = text.trim();
          const summary = trimmed
            ? generateDocumentSummary(text)
            : fallbackSummary(fileType);
          updateEntry(docId, {
            bytes,
            summary,
            textChars: trimmed.length,
            ...(pageCount ? { pageCount } : {}),
            status: "ready",
            detail:
              parseNote ||
              (trimmed
                ? "已生成摘要，可在提交前修改标题与摘要。"
                : "未提取到正文，可手动补写摘要后提交。"),
          });
        } catch (error) {
          updateEntry(docId, {
            status: "error",
            detail: `读取文件失败：${
              error instanceof Error ? error.message : String(error)
            }`,
          });
        }
      }
    },
    [applyEntries, updateEntry],
  );

  const ingestClipboardText = useCallback(
    (text: string) => {
      const docId = createChannelDocumentId();
      const firstLine =
        text
          .split("\n")
          .map((line) => line.trim())
          .find(Boolean) ?? "剪贴板文本";
      const bytes = new TextEncoder().encode(text);
      applyEntries((previous) => [
        ...previous,
        {
          key: docId,
          docId,
          fileName: clipboardFileName(new Date()),
          fileType: "text",
          fileSize: bytes.length,
          bytes,
          title: firstLine.slice(0, 120),
          summary: generateDocumentSummary(text),
          textChars: text.trim().length,
          status: "ready",
          detail: "剪贴板文本已就绪，可在提交前修改标题与摘要。",
        },
      ]);
    },
    [applyEntries],
  );

  const processedFilesRef = useRef<File[] | null>(null);
  useEffect(() => {
    if (!incomingFiles?.length) return;
    // Guard against StrictMode double-invocation re-ingesting the same drop.
    if (processedFilesRef.current === incomingFiles) return;
    processedFilesRef.current = incomingFiles;
    void ingestFiles(incomingFiles);
    onIncomingConsumed();
  }, [incomingFiles, ingestFiles, onIncomingConsumed]);

  useEffect(() => {
    if (!open) return;
    const onPaste = (event: ClipboardEvent) => {
      const files = Array.from(event.clipboardData?.files ?? []);
      if (files.length) {
        event.preventDefault();
        void ingestFiles(files);
        return;
      }
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable]")) return;
      const text = event.clipboardData?.getData("text/plain") ?? "";
      if (text.trim()) {
        event.preventDefault();
        ingestClipboardText(text);
      }
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [open, ingestFiles, ingestClipboardText]);

  function persistToken(value: string) {
    setToken(value);
    const trimmed = value.trim();
    if (trimmed) window.sessionStorage.setItem(TOKEN_SESSION_KEY, trimmed);
    else window.sessionStorage.removeItem(TOKEN_SESSION_KEY);
  }

  const performSave = useCallback(
    async (key: string, cleanToken: string) => {
      const entry = entriesRef.current.find((item) => item.key === key);
      if (!entry || entry.status !== "saving" || !entry.bytes) return;
      try {
        if (!usernameRef.current) {
          updateEntry(key, { detail: "正在验证管理员身份……" });
          const user = await githubJson<{ login: string }>(
            `${GITHUB_API_ROOT}/user`,
            cleanToken,
          );
          if (user.login.toLowerCase() !== TRACKING_OWNER.toLowerCase()) {
            throw new Error(
              `当前账号 ${user.login} 不是仓库所有者 ${TRACKING_OWNER}。`,
            );
          }
          usernameRef.current = user.login;
        }

        const safeName = safeChannelDocumentFileName(entry.fileName);
        const filePath = buildChannelDocumentPath(
          channel,
          entry.docId,
          safeName,
        );
        updateEntry(key, {
          detail: `正在上传文件（${sizeLabel(entry.fileSize)}）……`,
        });
        await putRepoFile(cleanToken, {
          repoPath: `public/${filePath}`,
          base64Content: bytesToBase64(entry.bytes),
          message: `docs: import ${safeName} into ${channel} channel updates`,
        });

        const uploadedAt = new Date().toISOString();
        const record: ChannelDocumentRecord = {
          id: entry.docId,
          channel,
          title: entry.title.trim() || entry.fileName,
          summary: entry.summary.trim(),
          fileName: entry.fileName,
          filePath,
          fileType: entry.fileType,
          fileSize: entry.fileSize,
          ...(entry.pageCount ? { pageCount: entry.pageCount } : {}),
          ...(entry.textChars ? { textChars: entry.textChars } : {}),
          uploadedAt,
          uploadedBy: usernameRef.current,
        };

        updateEntry(key, { detail: "正在更新文档索引……" });
        let commitSha = "";
        for (let attempt = 1; attempt <= 2; attempt += 1) {
          const manifest = await fetchRepoTextFile(
            cleanToken,
            CHANNEL_DOCUMENTS_PATH,
          );
          const payload = normalizeChannelDocuments(JSON.parse(manifest.text));
          const documents = [
            record,
            ...payload.documents.filter((item) => item.id !== record.id),
          ];
          try {
            const result = await putRepoFile(cleanToken, {
              repoPath: CHANNEL_DOCUMENTS_PATH,
              base64Content: textToBase64(
                `${JSON.stringify(
                  { schemaVersion: 1, generatedAt: uploadedAt, documents },
                  null,
                  2,
                )}\n`,
              ),
              message: `data: index imported document ${record.id}`,
              sha: manifest.sha,
            });
            commitSha = result.commitSha;
            break;
          } catch (error) {
            const status = (error as Error & { status?: number }).status;
            if (attempt === 1 && (status === 409 || status === 422)) continue;
            throw error;
          }
        }

        updateEntry(key, {
          status: "saved",
          detail: `已提交（${commitSha.slice(0, 8) || "commit"}）。站点重建完成后固定显示；当前列表内的链接先指向仓库原文件。`,
        });
        const item = channelDocumentToUpdateItem(record, uploadedAt);
        onSaved({
          ...item,
          href: `https://raw.githubusercontent.com/${TRACKING_REPOSITORY}/${TRACKING_BRANCH}/public/${record.filePath}`,
        });
      } catch (error) {
        updateEntry(key, {
          status: "ready",
          detail: `提交失败：${
            error instanceof Error ? error.message : String(error)
          }`,
        });
      }
    },
    [channel, onSaved, updateEntry],
  );

  const enqueueSave = useCallback(
    (key: string) => {
      const cleanToken = token.trim();
      const entry = entriesRef.current.find((item) => item.key === key);
      if (!entry || entry.status !== "ready" || !entry.bytes) return;
      if (!cleanToken) {
        updateEntry(key, {
          detail: "请先填写仓库管理员 Token（与 /tracking 管理页共用）。",
        });
        return;
      }
      updateEntry(key, { status: "saving", detail: "排队等待提交……" });
      queueRef.current = queueRef.current.then(() =>
        performSave(key, cleanToken),
      );
    },
    [performSave, token, updateEntry],
  );

  if (!open) return null;

  const readyCount = entries.filter((entry) => entry.status === "ready").length;

  return (
    <div className={styles.panel}>
      <div className={styles.panelHeader}>
        <div>
          <strong>文档信源导入</strong>
          <span>
            拖入或粘贴 PDF、Word、PPT、文本与截图，解析摘要后提交到仓库，成为本频道的可追溯信源。
          </span>
        </div>
        <button
          className={styles.iconButton}
          onClick={onClose}
          aria-label="关闭导入面板"
        >
          <X size={16} />
        </button>
      </div>

      <div className={styles.tokenRow}>
        <label>
          <span>管理员 Token</span>
          <input
            type="password"
            autoComplete="off"
            spellCheck={false}
            placeholder="Fine-grained Token · Contents: Read and write"
            value={token}
            onChange={(event) => persistToken(event.target.value)}
          />
        </label>
        <p>
          Token 只保存在当前标签页的 sessionStorage，与 /tracking 管理页共用一次登录；提交会直接写入
          main 分支并触发站点重建。
        </p>
      </div>

      <button
        type="button"
        className={styles.dropzone}
        onClick={() => fileInputRef.current?.click()}
      >
        <Upload size={18} aria-hidden="true" />
        <strong>拖拽文件到更新目录，或点击选择文件</strong>
        <span>支持 PDF / docx / doc / pptx / ppt / txt / md / 图片，单文件 ≤ 25MB；也可直接 Ctrl+V 粘贴文件、截图或文本。</span>
      </button>
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept={ACCEPTED_INPUT}
        className={styles.hiddenInput}
        onChange={(event) => {
          const files = Array.from(event.target.files ?? []);
          if (files.length) void ingestFiles(files);
          event.target.value = "";
        }}
      />

      {entries.length > 0 && (
        <div className={styles.queue}>
          {entries.map((entry) => (
            <article className={styles.entry} key={entry.key}>
              <div className={styles.entryHeader}>
                <span className={styles.badge}>
                  <FileText size={12} aria-hidden="true" />
                  {channelDocumentTypeLabel(entry.fileType)}
                </span>
                <span className={styles.fileName} title={entry.fileName}>
                  {entry.fileName}
                </span>
                <span className={styles.fileMeta}>
                  {sizeLabel(entry.fileSize)}
                  {entry.pageCount ? ` · ${entry.pageCount} 页` : ""}
                  {entry.textChars
                    ? ` · 正文 ${entry.textChars.toLocaleString("zh-CN")} 字`
                    : ""}
                </span>
                <button
                  className={styles.iconButton}
                  onClick={() =>
                    applyEntries((previous) =>
                      previous.filter((item) => item.key !== entry.key),
                    )
                  }
                  disabled={entry.status === "saving"}
                  aria-label={`移除 ${entry.fileName}`}
                >
                  <Trash2 size={14} />
                </button>
              </div>

              {(entry.status === "ready" ||
                entry.status === "saving" ||
                entry.status === "saved") && (
                <div className={styles.fields}>
                  <label>
                    <span>标题</span>
                    <input
                      value={entry.title}
                      maxLength={160}
                      disabled={entry.status !== "ready"}
                      onChange={(event) =>
                        updateEntry(entry.key, { title: event.target.value })
                      }
                    />
                  </label>
                  <label>
                    <span>摘要（展示在文件链接上方，可修改）</span>
                    <textarea
                      value={entry.summary}
                      rows={3}
                      maxLength={600}
                      disabled={entry.status !== "ready"}
                      onChange={(event) =>
                        updateEntry(entry.key, { summary: event.target.value })
                      }
                    />
                  </label>
                </div>
              )}

              <div className={styles.entryFooter}>
                <p
                  className={styles.status}
                  data-kind={
                    entry.status === "saved"
                      ? "success"
                      : entry.status === "error"
                        ? "error"
                        : "neutral"
                  }
                  aria-live="polite"
                >
                  {entry.detail}
                </p>
                {entry.status === "ready" && (
                  <button
                    className={styles.saveButton}
                    onClick={() => enqueueSave(entry.key)}
                  >
                    保存到仓库
                  </button>
                )}
              </div>
            </article>
          ))}

          {readyCount > 1 && (
            <button
              className={styles.saveAll}
              onClick={() => {
                for (const entry of entriesRef.current) {
                  if (entry.status === "ready") enqueueSave(entry.key);
                }
              }}
            >
              全部保存（{readyCount} 个）
            </button>
          )}
        </div>
      )}
    </div>
  );
}
