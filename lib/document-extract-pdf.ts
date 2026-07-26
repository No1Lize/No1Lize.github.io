// PDF text extraction runs only in the browser. pdfjs-dist is loaded on
// demand so channel pages don't pay for it until a PDF is actually dropped.
// The worker is vendored at public/vendor/pdf.worker.min.mjs and must stay on
// the same version as the pdfjs-dist dependency in package.json.

export const PDF_WORKER_PATH = "/vendor/pdf.worker.min.mjs";
// CJK PDFs use CID-keyed fonts; without these packed CMaps getTextContent
// returns mojibake. Both directories are vendored from the same pdfjs-dist
// version as the worker.
export const PDF_CMAP_PATH = "/vendor/cmaps/";
export const PDF_STANDARD_FONT_PATH = "/vendor/standard_fonts/";

// Reading every page of a large PDF is wasteful for a short summary; the
// opening pages carry the abstract and key findings.
const MAX_TEXT_PAGES = 40;

export async function extractPdfDocument(
  data: Uint8Array,
): Promise<{ text: string; pageCount: number }> {
  const pdfjs = await import("pdfjs-dist");
  if (!pdfjs.GlobalWorkerOptions.workerSrc) {
    pdfjs.GlobalWorkerOptions.workerSrc = PDF_WORKER_PATH;
  }
  // getDocument may transfer the buffer to the worker; keep the caller's copy.
  const task = pdfjs.getDocument({
    data: data.slice(),
    cMapUrl: PDF_CMAP_PATH,
    cMapPacked: true,
    standardFontDataUrl: PDF_STANDARD_FONT_PATH,
  });
  const document = await task.promise;
  try {
    const pageCount = document.numPages;
    const limit = Math.min(pageCount, MAX_TEXT_PAGES);
    const parts: string[] = [];
    for (let pageNumber = 1; pageNumber <= limit; pageNumber += 1) {
      const page = await document.getPage(pageNumber);
      const content = await page.getTextContent();
      const pageText = content.items
        .map((item) => ("str" in item ? item.str : ""))
        .join(" ");
      if (pageText.trim()) parts.push(pageText);
      page.cleanup();
    }
    return { text: parts.join("\n"), pageCount };
  } finally {
    await task.destroy();
  }
}
