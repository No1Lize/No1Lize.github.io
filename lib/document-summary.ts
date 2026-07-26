export const DOCUMENT_SUMMARY_MAX_LENGTH = 180;

const SENTENCE_BOUNDARY = /(?<=[。！？!?；;])\s*|\n+/u;
const CONTROL_CHARS =
  /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F\uFEFF]/g;
const SPACE_RUNS = /[	   -​　]+/g;

/**
 * Whether extracted text is trustworthy enough to summarize. PDFs exported by
 * macOS Quartz (and some scanners) embed subset CJK fonts without ToUnicode
 * maps, so extraction yields symbol soup no summarizer should ever see.
 */
export function isMostlyLegibleText(rawText: string): boolean {
  const text = rawText.replace(/\s+/g, "");
  if (text.length < 40) return false;
  const sample = text.slice(0, 4000);
  const legible = (sample.match(/[A-Za-z0-9㐀-鿿，。、；：？！""''（）%¥$€.\-,:;()/]/gu) ?? [])
    .length;
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
 * Frequency-scored extractive summary: pick the most informative sentences
 * and keep them in the original order, capped to maxLength characters. Runs
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
    const normalized = score / Math.sqrt(Math.max(terms.length, 1));
    const positionBoost = index < 12 ? 1.25 : index < 40 ? 1.08 : 1;
    return { sentence, index, score: normalized * positionBoost };
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

  const summary = picked
    .sort((left, right) => left.index - right.index)
    .map((entry) => entry.sentence)
    .join(" ");
  const withPunctuation = /[。！？!?；;.]$/.test(summary)
    ? summary
    : `${summary}。`;
  return withPunctuation.length > maxLength
    ? `${withPunctuation.slice(0, maxLength - 1)}…`
    : withPunctuation;
}
