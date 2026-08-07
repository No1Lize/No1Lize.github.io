#!/usr/bin/env node
import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";

const ROOT = process.cwd();
const INPUT = path.join(ROOT, "public", "data", "articles.json");
const OUTPUT = path.join(ROOT, "public", "data", "article_search_index.json");

function cleanText(value, maxLength = 320) {
  if (typeof value !== "string") return "";
  return value.normalize("NFKC").replace(/\s+/g, " ").trim().slice(0, maxLength);
}

const payload = JSON.parse(readFileSync(INPUT, "utf8"));
const articles = Array.isArray(payload?.articles) ? payload.articles : [];

const records = articles.flatMap((article) => {
  const title = cleanText(article?.title, 240);
  const company = cleanText(article?.company, 120);
  const sector = cleanText(article?.sector, 100);
  const eventType = cleanText(article?.type, 60);
  const region = cleanText(article?.region, 40) || "全球";
  const sourceName = cleanText(article?.source?.name, 120);
  const publishedAt = cleanText(article?.publishedAt, 20);
  const summary = cleanText(article?.summary, 240);
  const href = article?.companySlug
    ? `/companies/${cleanText(article.companySlug, 160)}`
    : cleanText(article?.source?.url, 1000);

  if (!title || !href) return [];

  return [{
    type: "事件",
    title,
    text: [summary, company, sector, eventType, region, sourceName, publishedAt]
      .filter(Boolean)
      .join(" · "),
    href,
    region,
  }];
});

const output = {
  schemaVersion: 1,
  generatedAt: typeof payload?.generatedAt === "string" ? payload.generatedAt : "",
  recordCount: records.length,
  records,
};

writeFileSync(OUTPUT, `${JSON.stringify(output)}\n`, "utf8");
console.log(`Built article search index: ${records.length} records -> ${path.relative(ROOT, OUTPUT)}`);
