import { readFile } from "node:fs/promises";
import path from "node:path";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { FavoriteButton } from "@/components/favorite-button";
import {
  channelDocumentTypeLabel,
  getAllChannelDocuments,
  getChannelDocumentById,
  type ChannelDocumentRecord,
} from "@/lib/channel-documents";
import {
  extractDocxDocument,
  extractPptxDocument,
} from "@/lib/document-extract";
import { cleanExtractedText, isMostlyLegibleText } from "@/lib/document-summary";

const CHANNEL_LINKS: Record<ChannelDocumentRecord["channel"], [string, string]> = {
  technology: ["新兴科技", "/technology"],
  companies: ["创业案例", "/companies"],
  institutions: ["投资机构", "/institutions"],
  reports: ["研究报告", "/reports"],
  people: ["人物研究", "/people"],
};

const PREVIEW_CHAR_LIMIT = 30000;

export function generateStaticParams() {
  return getAllChannelDocuments().map((record) => ({ id: record.id }));
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ id: string }>;
}): Promise<Metadata> {
  const { id } = await params;
  const record = getChannelDocumentById(id);
  return {
    title: record ? record.title : "文档信源",
    description: record?.summary?.slice(0, 120),
  };
}

function sizeLabel(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

async function buildTextPreview(
  record: ChannelDocumentRecord,
): Promise<string | null> {
  if (!["text", "docx", "pptx"].includes(record.fileType)) return null;
  try {
    const absolute = path.join(process.cwd(), "public", record.filePath);
    const data = new Uint8Array(await readFile(absolute));
    let text = "";
    if (record.fileType === "text") {
      text = new TextDecoder().decode(data);
    } else if (record.fileType === "docx") {
      text = (await extractDocxDocument(data)).text;
    } else {
      text = (await extractPptxDocument(data)).text;
    }
    const cleaned = cleanExtractedText(text);
    if (!cleaned || !isMostlyLegibleText(cleaned)) return null;
    return cleaned.length > PREVIEW_CHAR_LIMIT
      ? `${cleaned.slice(0, PREVIEW_CHAR_LIMIT)}\n……（预览截断，完整内容请下载原文件）`
      : cleaned;
  } catch {
    return null;
  }
}

export default async function DocumentReaderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const record = getChannelDocumentById(id);
  if (!record) notFound();

  const [channelName, channelHref] = CHANNEL_LINKS[record.channel];
  const fileHref = `/${record.filePath}`;
  const textPreview = await buildTextPreview(record);

  return (
    <main className="page-shell subpage document-reader">
      <header className="page-header">
        <p className="eyebrow">DOCUMENT SOURCE · 手动导入信源</p>
        <div className="detail-title-row">
          <h1>{record.title}</h1>
          <FavoriteButton
            item={{
              id: `document:${record.id}`,
              href: `/documents/${record.id}`,
              title: record.title,
              summary: record.summary,
              channel: record.channel,
              channelLabel: channelName,
              keywords: [],
              sectors: [],
              sources: [],
              region: "全球",
            }}
          />
        </div>
        <p className="document-reader-meta">
          {channelDocumentTypeLabel(record.fileType)} · {record.fileName} ·{" "}
          {sizeLabel(record.fileSize)}
          {record.pageCount ? ` · ${record.pageCount} 页` : ""} · 导入于{" "}
          {record.uploadedAt.slice(0, 10)}
        </p>
        <Link className="text-link" href={channelHref}>
          ← 返回{channelName}频道
        </Link>
      </header>

      <section className="data-panel document-reader-summary">
        <div className="section-heading compact">
          <div>
            <p className="section-index">SUMMARY</p>
            <h2>摘要</h2>
          </div>
          <span>本地抽取式摘要 · 提交时可人工修订</span>
        </div>
        <p>{record.summary}</p>
        <div className="document-reader-actions">
          <a
            className="document-download"
            href={fileHref}
            download={record.fileName}
          >
            下载原文件
          </a>
          <a href={fileHref} rel="noreferrer" target="_blank">
            在新标签页打开原始文件 ↗
          </a>
        </div>
      </section>

      <section className="data-panel">
        <div className="section-heading compact">
          <div>
            <p className="section-index">PREVIEW</p>
            <h2>在线阅读</h2>
          </div>
          <span>浏览器内预览，不会自动下载</span>
        </div>
        {record.fileType === "pdf" ? (
          <iframe
            className="document-preview-frame"
            src={`${fileHref}#view=FitH`}
            title={`${record.title} PDF 预览`}
          />
        ) : record.fileType === "image" ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            className="document-preview-image"
            src={fileHref}
            alt={record.title}
          />
        ) : textPreview ? (
          <pre className="document-preview-text">{textPreview}</pre>
        ) : (
          <div className="empty-state">
            <strong>此格式暂不支持浏览器内预览</strong>
            <p>
              {record.fileType === "doc" || record.fileType === "ppt"
                ? "旧版 Office 二进制格式需要下载后用本地办公软件打开。"
                : "未能提取可读正文，请下载原文件查看。"}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
