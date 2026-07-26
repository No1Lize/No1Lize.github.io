export const DOCUMENT_SUMMARY_MAX_LENGTH = 180;

const SENTENCE_BOUNDARY = /(?<=[。！？!?；;])\s*|\n+/u;
const CONTROL_CHARS =
  /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\uFEFF]/g;
const SPACE_RUNS = /[	   -​　]+/g;

// Sentences that carry a research report's substance: conclusions, forecasts,
// operating and valuation metrics. Both languages are boosted the same way.
const REPORT_SIGNALS =
  /我们认为|核心观点|结论|综上|预计|预期|测算|盈利预测|目标价|建议关注|风险提示|驱动|受益|同比|环比|毛利率|净利率|市占率|渗透率|产能|出货量|良率|资本开支|估值|复合增长/u;
const REPORT_SIGNALS_EN =
  /\b(?:we\s+(?:expect|estimate|believe)|forecasts?|guidance|outlook|revenue|margins?|market\s+share|capex|valuation|risks?|CAGR)\b/i;
const QUANT_SIGNAL = /\d+(?:\.\d+)?\s*(?:%|亿|万|百万|亿元|万元|美元|元|GWh|nm|TB|GB)|20\d{2}\s*年/u;
// Table-of-contents dot leaders and bare section numbering are page furniture.
const FURNITURE = /(?:\.{4,}|…{2,}|·{4,})|^目\s*录$|^第[一二三四五六七八九十\d]+\s*[章节部分篇]\s*$|^\d+(?:\.\d+)*\s*$/u;

/**
 * Whether extracted text is trustworthy enough to summarize. PDFs exported by
 * macOS Quartz (and some scanners) embed subset CJK fonts without ToUnicode
 * maps; extraction then yields symbol soup in which plain ASCII (digits,
 * percent signs, stray Latin) survives while every CJK glyph is mangled into
 * extended-Latin/math symbols — so the check keys on that symbol ratio rather
 * than on how much ASCII remains.
 */
export function isMostlyLegibleText(rawText: string): boolean {
  const text = rawText.replace(/\s+/g, "");
  if (text.length < 40) return false;
  const sample = text.slice(0, 4000);
  const weird = (
    sample.match(
      /[¡-ɏʰ-ͯ΄-Ͽ⁰-₟∀-⋿─-◿ﬀ-ﭏ]/gu,
    ) ?? []
  ).length;
  if (weird / sample.length > 0.08) return false;
  const legible = (
    sample.match(
      /[A-Za-z0-9㐀-鿿，。、；：？！“”‘’（）《》%¥$€.\-,:;()/+&#]/gu,
    ) ?? []
  ).length;
  return legible / sample.length >= 0.6;
}

export function cleanExtractedText(raw: string): string {
  return raw
    .replace(/\r\n?/g, "\n")
    .replace(CONTROL_CHARS, " ")
    .replace(SPACE_RUNS, " ")
    .replace(/ ?\n ?/g, "\n")
    .replace(/\n{2,}/g, "\n")
    .trim();
}

function splitSentences(text: string): string[] {
  return text
    .split(SENTENCE_BOUNDARY)
    .map((sentence) => sentence.trim())
    .filter((sentence) => {
      if (sentence.length < 8) return false;
      if (FURNITURE.test(sentence)) return false;
      const informative = sentence.replace(/[^\p{L}\p{N}]+/gu, "");
      if (informative.length < 6) return false;
      // Drop lines that are mostly page furniture: bare numbers and dates.
      return /\p{L}/u.test(sentence);
    });
}

function extractTerms(sentence: string): string[] {
  const terms: string[] = [];
  const lowered = sentence.toLocaleLowerCase("zh-CN");
  for (const match of lowered.matchAll(/[a-z0-9][a-z0-9.-]{1,}/g)) {
    if (match[0].length >= 2) terms.push(match[0]);
  }
  const cjkRuns = lowered.match(/[㐀-鿿]+/gu) ?? [];
  for (const run of cjkRuns) {
    for (let index = 0; index < run.length - 1; index += 1) {
      terms.push(run.slice(index, index + 2));
    }
  }
  return terms;
}

/**
 * Frequency-scored extractive summary tuned for research material: sentences
 * that state conclusions, forecasts or quantified metrics outrank generic
 * prose, TOC noise is dropped, and the picks keep their original order. Runs
 * fully client-side so imported files never leave the browser before commit.
 */
export function generateDocumentSummary(
  rawText: string,
  maxLength: number = DOCUMENT_SUMMARY_MAX_LENGTH,
): string {
  const text = cleanExtractedText(rawText);
  if (!text) return "";

  const sentences = splitSentences(text);
  if (!sentences.length) {
    return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
  }

  const frequency = new Map<string, number>();
  const sentenceTerms = sentences.map((sentence) => extractTerms(sentence));
  for (const terms of sentenceTerms) {
    for (const term of terms) {
      frequency.set(term, (frequency.get(term) ?? 0) + 1);
    }
  }

  const scored = sentences.map((sentence, index) => {
    const terms = sentenceTerms[index];
    let score = 0;
    for (const term of terms) score += frequency.get(term) ?? 0;
    // Normalize long sentences and favor the opening of the document, where
    // abstracts and executive summaries usually live.
    let weight = score / Math.sqrt(Math.max(terms.length, 1));
    weight *= index < 12 ? 1.25 : index < 40 ? 1.08 : 1;
    if (REPORT_SIGNALS.test(sentence) || REPORT_SIGNALS_EN.test(sentence)) {
      weight *= 1.35;
    }
    if (QUANT_SIGNAL.test(sentence)) weight *= 1.15;
    const letters = (sentence.match(/[\p{L}]/gu) ?? []).length;
    if (letters / sentence.length < 0.5) weight *= 0.7;
    return { sentence, index, score: weight };
  });

  const byScore = [...scored].sort(
    (left, right) => right.score - left.score || left.index - right.index,
  );
  const picked: { sentence: string; index: number }[] = [];
  let total = 0;
  for (const candidate of byScore) {
    if (picked.length >= 3) break;
    const addition = candidate.sentence.length + (picked.length ? 1 : 0);
    if (picked.length && total + addition > maxLength) continue;
    picked.push(candidate);
    total += addition;
    if (total >= maxLength) break;
  }
  if (!picked.length) picked.push(byScore[0]);

  const ordered = picked
    .sort((left, right) => left.index - right.index)
    .map((entry) => entry.sentence.replace(/[；;]$/u, ""));
  const cjkDominant =
    (ordered.join("").match(/[㐀-鿿]/gu) ?? []).length >
    ordered.join("").length / 4;
  const summary = ordered.join(cjkDominant ? "；" : " ");
  const withPunctuation = /[。！？!?.]$/.test(summary)
    ? summary
    : `${summary}。`;
  return withPunctuation.length > maxLength
    ? `${withPunctuation.slice(0, maxLength - 1)}…`
    : withPunctuation;
}
