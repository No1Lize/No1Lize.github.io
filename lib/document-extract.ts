// Client-side text extraction for imported OOXML documents. The zip reader
// and XML text walkers rely only on web-standard APIs (DataView, Blob,
// DecompressionStream), so the same code runs in the browser and in Node
// unit tests without adding a zip dependency.

const EOCD_SIGNATURE = 0x06054b50;
const CENTRAL_SIGNATURE = 0x02014b50;
const LOCAL_SIGNATURE = 0x04034b50;
const MAX_EOCD_SCAN = 65557;

export type ZipEntry = {
  name: string;
  compressionMethod: number;
  compressedSize: number;
  uncompressedSize: number;
  localHeaderOffset: number;
};

async function inflateRaw(bytes: Uint8Array): Promise<Uint8Array> {
  const stream = new Blob([bytes as BlobPart])
    .stream()
    .pipeThrough(new DecompressionStream("deflate-raw"));
  const buffer = await new Response(stream).arrayBuffer();
  return new Uint8Array(buffer);
}

export function listZipEntries(data: Uint8Array): ZipEntry[] {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const scanStart = Math.max(0, data.length - MAX_EOCD_SCAN);
  let eocdOffset = -1;
  for (let offset = data.length - 22; offset >= scanStart; offset -= 1) {
    if (view.getUint32(offset, true) === EOCD_SIGNATURE) {
      eocdOffset = offset;
      break;
    }
  }
  if (eocdOffset < 0) {
    throw new Error("不是有效的 ZIP 容器（未找到目录结尾标记）。");
  }

  const entryCount = view.getUint16(eocdOffset + 10, true);
  const centralSize = view.getUint32(eocdOffset + 12, true);
  const centralOffset = view.getUint32(eocdOffset + 16, true);
  if (centralOffset === 0xffffffff || entryCount === 0xffff) {
    throw new Error("暂不支持 ZIP64 格式的文档。");
  }
  if (centralOffset + centralSize > data.length) {
    throw new Error("ZIP 中央目录越界，文件可能已损坏。");
  }

  const decoder = new TextDecoder();
  const entries: ZipEntry[] = [];
  let cursor = centralOffset;
  for (let index = 0; index < entryCount; index += 1) {
    if (view.getUint32(cursor, true) !== CENTRAL_SIGNATURE) {
      throw new Error("ZIP 中央目录记录损坏。");
    }
    const compressionMethod = view.getUint16(cursor + 10, true);
    const compressedSize = view.getUint32(cursor + 20, true);
    const uncompressedSize = view.getUint32(cursor + 24, true);
    const nameLength = view.getUint16(cursor + 28, true);
    const extraLength = view.getUint16(cursor + 30, true);
    const commentLength = view.getUint16(cursor + 32, true);
    const localHeaderOffset = view.getUint32(cursor + 42, true);
    const name = decoder.decode(
      data.subarray(cursor + 46, cursor + 46 + nameLength),
    );
    entries.push({
      name,
      compressionMethod,
      compressedSize,
      uncompressedSize,
      localHeaderOffset,
    });
    cursor += 46 + nameLength + extraLength + commentLength;
  }
  return entries;
}

export async function readZipEntry(
  data: Uint8Array,
  entry: ZipEntry,
): Promise<Uint8Array> {
  const view = new DataView(data.buffer, data.byteOffset, data.byteLength);
  const offset = entry.localHeaderOffset;
  if (view.getUint32(offset, true) !== LOCAL_SIGNATURE) {
    throw new Error(`ZIP 条目 ${entry.name} 的本地头损坏。`);
  }
  const nameLength = view.getUint16(offset + 26, true);
  const extraLength = view.getUint16(offset + 28, true);
  const start = offset + 30 + nameLength + extraLength;
  const compressed = data.subarray(start, start + entry.compressedSize);
  if (entry.compressionMethod === 0) return compressed.slice();
  if (entry.compressionMethod === 8) return inflateRaw(compressed);
  throw new Error(
    `ZIP 条目 ${entry.name} 使用了不支持的压缩方式 ${entry.compressionMethod}。`,
  );
}

async function readZipTextEntry(
  data: Uint8Array,
  entry: ZipEntry,
): Promise<string> {
  return new TextDecoder().decode(await readZipEntry(data, entry));
}

export function decodeXmlEntities(value: string): string {
  return value.replace(
    /&(amp|lt|gt|quot|apos|#x[0-9a-fA-F]+|#\d+);/g,
    (match, entity: string) => {
      switch (entity) {
        case "amp":
          return "&";
        case "lt":
          return "<";
        case "gt":
          return ">";
        case "quot":
          return '"';
        case "apos":
          return "'";
        default: {
          const code = entity.startsWith("#x")
            ? Number.parseInt(entity.slice(2), 16)
            : Number.parseInt(entity.slice(1), 10);
          return Number.isFinite(code) && code > 0
            ? String.fromCodePoint(code)
            : match;
        }
      }
    },
  );
}

/**
 * Walk WordprocessingML in document order: text runs, tabs, breaks and
 * paragraph ends. Regex tokenization is deliberate — it keeps the extractor
 * dependency-free and works in Node tests where DOMParser is unavailable.
 */
export function extractDocxXmlText(xml: string): string {
  const tokens = xml.match(
    /<w:t(?:\s[^>]*)?>[\s\S]*?<\/w:t>|<\/w:p>|<w:tab\b[^>]*\/>|<w:br\b[^>]*\/>|<w:cr\b[^>]*\/>/g,
  );
  if (!tokens) return "";
  let text = "";
  for (const token of tokens) {
    if (token === "</w:p>") {
      text += "\n";
    } else if (token.startsWith("<w:tab")) {
      text += "\t";
    } else if (token.startsWith("<w:br") || token.startsWith("<w:cr")) {
      text += "\n";
    } else {
      const inner = token.replace(/^<w:t(?:\s[^>]*)?>/, "").replace(/<\/w:t>$/, "");
      text += decodeXmlEntities(inner);
    }
  }
  return text;
}

export function extractPptxXmlText(xml: string): string {
  const tokens = xml.match(/<a:t>[\s\S]*?<\/a:t>|<\/a:p>/g);
  if (!tokens) return "";
  let text = "";
  for (const token of tokens) {
    if (token === "</a:p>") {
      text += "\n";
    } else {
      text += decodeXmlEntities(token.slice(5, -6));
    }
  }
  return text;
}

export async function extractDocxDocument(
  data: Uint8Array,
): Promise<{ text: string }> {
  const entries = listZipEntries(data);
  const documentEntry = entries.find(
    (entry) => entry.name === "word/document.xml",
  );
  if (!documentEntry) {
    throw new Error("docx 中缺少 word/document.xml，可能不是有效的 Word 文档。");
  }
  const xml = await readZipTextEntry(data, documentEntry);
  return { text: extractDocxXmlText(xml) };
}

export async function extractPptxDocument(
  data: Uint8Array,
): Promise<{ text: string; slideCount: number }> {
  const entries = listZipEntries(data);
  const slides = entries
    .map((entry) => {
      const match = entry.name.match(/^ppt\/slides\/slide(\d+)\.xml$/);
      return match ? { entry, order: Number.parseInt(match[1], 10) } : null;
    })
    .filter((value): value is { entry: ZipEntry; order: number } =>
      Boolean(value),
    )
    .sort((left, right) => left.order - right.order);
  if (!slides.length) {
    throw new Error("pptx 中没有找到幻灯片，可能不是有效的 PowerPoint 文档。");
  }
  const parts: string[] = [];
  for (const slide of slides) {
    const xml = await readZipTextEntry(data, slide.entry);
    const text = extractPptxXmlText(xml).trim();
    if (text) parts.push(text);
  }
  return { text: parts.join("\n\n"), slideCount: slides.length };
}
