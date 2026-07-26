import assert from "node:assert/strict";
import test from "node:test";
import { crc32, deflateRawSync } from "node:zlib";

import {
  buildChannelDocumentPath,
  channelDocumentToUpdateItem,
  createChannelDocumentId,
  detectChannelDocumentFileType,
  normalizeChannelDocuments,
  safeChannelDocumentFileName,
  type ChannelDocumentRecord,
} from "../lib/channel-documents";
import {
  decodeXmlEntities,
  extractDocxDocument,
  extractDocxXmlText,
  extractPptxDocument,
  extractPptxXmlText,
  listZipEntries,
} from "../lib/document-extract";
import {
  cleanExtractedText,
  generateDocumentSummary,
} from "../lib/document-summary";

const validRecord: ChannelDocumentRecord = {
  id: "doc-20260726-120000-ab12",
  channel: "technology",
  title: "固态电池产业调研",
  summary: "覆盖正极材料与电解质路线的对比分析。",
  fileName: "固态电池调研.pdf",
  filePath: "data/uploads/technology/doc-20260726-120000-ab12-固态电池调研.pdf",
  fileType: "pdf",
  fileSize: 1024,
  pageCount: 12,
  uploadedAt: "2026-07-26T12:00:00.000Z",
};

function buildZip(
  entries: [string, string][],
  options: { deflate?: boolean } = {},
): Uint8Array {
  const encoder = new TextEncoder();
  const chunks: Uint8Array[] = [];
  const central: {
    nameBytes: Uint8Array;
    method: number;
    checksum: number;
    storedLength: number;
    rawLength: number;
    offset: number;
  }[] = [];
  let offset = 0;
  for (const [name, content] of entries) {
    const nameBytes = encoder.encode(name);
    const raw = encoder.encode(content);
    const stored = options.deflate ? deflateRawSync(raw) : raw;
    const method = options.deflate ? 8 : 0;
    const checksum = crc32(raw);
    const local = new Uint8Array(30 + nameBytes.length + stored.length);
    const view = new DataView(local.buffer);
    view.setUint32(0, 0x04034b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(8, method, true);
    view.setUint32(14, checksum, true);
    view.setUint32(18, stored.length, true);
    view.setUint32(22, raw.length, true);
    view.setUint16(26, nameBytes.length, true);
    local.set(nameBytes, 30);
    local.set(stored, 30 + nameBytes.length);
    chunks.push(local);
    central.push({
      nameBytes,
      method,
      checksum,
      storedLength: stored.length,
      rawLength: raw.length,
      offset,
    });
    offset += local.length;
  }
  const centralStart = offset;
  for (const entry of central) {
    const record = new Uint8Array(46 + entry.nameBytes.length);
    const view = new DataView(record.buffer);
    view.setUint32(0, 0x02014b50, true);
    view.setUint16(4, 20, true);
    view.setUint16(6, 20, true);
    view.setUint16(10, entry.method, true);
    view.setUint32(16, entry.checksum, true);
    view.setUint32(20, entry.storedLength, true);
    view.setUint32(24, entry.rawLength, true);
    view.setUint16(28, entry.nameBytes.length, true);
    view.setUint32(42, entry.offset, true);
    record.set(entry.nameBytes, 46);
    chunks.push(record);
    offset += record.length;
  }
  const eocd = new Uint8Array(22);
  const view = new DataView(eocd.buffer);
  view.setUint32(0, 0x06054b50, true);
  view.setUint16(8, central.length, true);
  view.setUint16(10, central.length, true);
  view.setUint32(12, offset - centralStart, true);
  view.setUint32(16, centralStart, true);
  chunks.push(eocd);
  const total = new Uint8Array(offset + 22);
  let cursor = 0;
  for (const chunk of chunks) {
    total.set(chunk, cursor);
    cursor += chunk.length;
  }
  return total;
}

test("normalizeChannelDocuments keeps valid records and rejects unsafe ones", () => {
  const payload = normalizeChannelDocuments({
    schemaVersion: 1,
    generatedAt: "2026-07-26T12:00:00.000Z",
    documents: [
      validRecord,
      { ...validRecord, id: "doc-bad-channel", channel: "ipo" },
      {
        ...validRecord,
        id: "doc-bad-path",
        filePath: "data/uploads/technology/../../secrets.pdf",
      },
      {
        ...validRecord,
        id: "doc-outside-uploads",
        filePath: "config/user_tracking.json",
      },
      { ...validRecord },
      { ...validRecord, id: "doc-no-title", title: "  " },
    ],
  });
  assert.equal(payload.generatedAt, "2026-07-26T12:00:00.000Z");
  assert.deepEqual(
    payload.documents.map((record) => record.id),
    [validRecord.id],
  );
});

test("normalizeChannelDocuments tolerates malformed payloads", () => {
  assert.deepEqual(normalizeChannelDocuments(null).documents, []);
  assert.deepEqual(normalizeChannelDocuments("junk").documents, []);
  assert.equal(normalizeChannelDocuments({ generatedAt: "无效" }).generatedAt, "");
});

test("channelDocumentToUpdateItem renders the summary above the file link", () => {
  const item = channelDocumentToUpdateItem(validRecord, "2026-07-26T12:00:00.000Z");
  assert.equal(item.title, "固态电池产业调研");
  assert.equal(item.summary, "覆盖正极材料与电解质路线的对比分析。");
  assert.equal(
    item.href,
    "/data/uploads/technology/doc-20260726-120000-ab12-固态电池调研.pdf",
  );
  assert.equal(item.label, "PDF文档");
  assert.equal(item.source, "手动导入");
  assert.equal(item.context, "固态电池调研.pdf · 12 页");
  assert.equal(item.date, "2026-07-26");
  assert.deepEqual(item.keywords, ["PDF文档"]);
});

test("channelDocumentToUpdateItem falls back when the summary is empty", () => {
  const item = channelDocumentToUpdateItem(
    { ...validRecord, summary: "", pageCount: undefined },
    "2026-07-26T12:00:00.000Z",
  );
  assert.equal(item.summary, "已归档文件，未提取正文摘要。");
  assert.equal(item.context, "固态电池调研.pdf");
});

test("detectChannelDocumentFileType maps extensions and mime types", () => {
  assert.equal(detectChannelDocumentFileType("研报.PDF"), "pdf");
  assert.equal(detectChannelDocumentFileType("纪要.docx"), "docx");
  assert.equal(detectChannelDocumentFileType("老文档.doc"), "doc");
  assert.equal(detectChannelDocumentFileType("路演.pptx"), "pptx");
  assert.equal(detectChannelDocumentFileType("旧路演.ppt"), "ppt");
  assert.equal(detectChannelDocumentFileType("notes.md"), "text");
  assert.equal(detectChannelDocumentFileType("截图.png"), "image");
  assert.equal(
    detectChannelDocumentFileType("blob", "application/pdf"),
    "pdf",
  );
  assert.equal(detectChannelDocumentFileType("image", "image/webp"), "image");
  assert.equal(detectChannelDocumentFileType("archive.zip"), null);
});

test("safeChannelDocumentFileName keeps CJK and strips unsafe characters", () => {
  assert.equal(
    safeChannelDocumentFileName("2026 半年度 AI 报告 (final)?.PDF"),
    "2026-半年度-AI-报告-final.pdf",
  );
  assert.equal(safeChannelDocumentFileName("###.docx"), "document.docx");
  assert.equal(safeChannelDocumentFileName("固态电池·调研.pptx"), "固态电池·调研.pptx");
});

test("document ids and upload paths are deterministic", () => {
  const id = createChannelDocumentId(
    new Date("2026-07-26T12:34:56.000Z"),
    0.5,
  );
  assert.match(id, /^doc-20260726-123456-[a-z0-9]{4}$/);
  assert.equal(
    buildChannelDocumentPath("reports", id, "研报.pdf"),
    `data/uploads/reports/${id}-研报.pdf`,
  );
});

test("generateDocumentSummary extracts informative sentences in order", () => {
  const text = [
    "封面页 2026",
    "本报告研究中美具身智能产业的落地路径与供应链结构。",
    "目录",
    "第一章介绍执行器与传感器的国产化率变化，第二章给出估值框架。",
    "免责声明详见文末。",
  ].join("\n");
  const summary = generateDocumentSummary(text);
  assert.ok(summary.includes("具身智能"));
  assert.ok(summary.indexOf("具身智能") < summary.indexOf("估值框架"));
  assert.ok(summary.length <= 180);
});

test("generateDocumentSummary caps length and handles empty input", () => {
  assert.equal(generateDocumentSummary("   \n  "), "");
  const long = "这是一句会不断重复的完整描述性句子，用来验证摘要长度上限逻辑。".repeat(20);
  const summary = generateDocumentSummary(long, 120);
  assert.ok(summary.length <= 120);
  assert.ok(summary.endsWith("…") || summary.endsWith("。"));
});

test("cleanExtractedText collapses layout whitespace", () => {
  assert.equal(
    cleanExtractedText("第一行 内容  \r\n\r\n\r\n第二行\t文本　结尾"),
    "第一行 内容\n第二行 文本 结尾",
  );
});

test("decodeXmlEntities handles named and numeric entities", () => {
  assert.equal(
    decodeXmlEntities("A&amp;B &lt;C&gt; &quot;D&quot; &#x4E2D;&#25991;"),
    'A&B <C> "D" 中文',
  );
});

test("extractDocxXmlText follows runs, tabs, breaks and paragraphs", () => {
  const xml =
    '<w:p><w:r><w:t xml:space="preserve">段落一 </w:t></w:r><w:tab/><w:r><w:t>接排</w:t></w:r><w:br/></w:p><w:p><w:r><w:t>段落二&amp;补充</w:t></w:r></w:p>';
  assert.equal(extractDocxXmlText(xml), "段落一 \t接排\n\n段落二&补充\n");
});

test("extractPptxXmlText joins text runs per paragraph", () => {
  const xml = "<a:p><a:r><a:t>标题</a:t></a:r></a:p><a:p><a:r><a:t>要点</a:t></a:r></a:p>";
  assert.equal(extractPptxXmlText(xml), "标题\n要点\n");
});

test("extractDocxDocument reads deflated word/document.xml from the zip", async () => {
  const xml =
    "<w:document><w:body><w:p><w:r><w:t>中文正文与 AI&amp;算力 数据。</w:t></w:r></w:p></w:body></w:document>";
  const zip = buildZip(
    [
      ["[Content_Types].xml", "<Types/>"],
      ["word/document.xml", xml],
    ],
    { deflate: true },
  );
  const parsed = await extractDocxDocument(zip);
  assert.equal(parsed.text.trim(), "中文正文与 AI&算力 数据。");
});

test("extractPptxDocument orders slides numerically and counts them", async () => {
  const slide = (value: string) =>
    `<p:sld><a:p><a:r><a:t>${value}</a:t></a:r></a:p></p:sld>`;
  const zip = buildZip([
    ["ppt/slides/slide10.xml", slide("第十页")],
    ["ppt/slides/slide2.xml", slide("第二页")],
    ["ppt/slides/slide1.xml", slide("首页")],
    ["ppt/media/image1.png", "binary"],
  ]);
  const parsed = await extractPptxDocument(zip);
  assert.equal(parsed.slideCount, 3);
  assert.deepEqual(parsed.text.split("\n\n"), ["首页", "第二页", "第十页"]);
});

test("listZipEntries rejects non-zip payloads", () => {
  assert.throws(() => listZipEntries(new TextEncoder().encode("not a zip")), {
    message: /ZIP/,
  });
});
