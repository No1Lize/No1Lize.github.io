import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import {
  companies,
  institutionCatalog,
  ipoCompanies,
  people,
  reports,
} from "../lib/catalog-data";
import {
  intelligenceEvents,
  sectors,
  snapshotDate,
} from "../lib/intelligence-data";

const sources = Array.from(
  new Map(
    [
      ...companies.map((item) => item.source),
      ...institutionCatalog.map((item) => item.source),
      ...ipoCompanies.map((item) => item.source),
      ...intelligenceEvents.map((item) => item.source),
    ].map((source) => [source.url, source]),
  ).values(),
).map((source, index) => ({
  id: `source-${String(index + 1).padStart(3, "0")}`,
  ...source,
  access_method: "html",
  is_enabled: true,
}));

const snapshot = {
  updated_at: `${snapshotDate}T00:00:00+08:00`,
  formula_version: "heat-v1",
  events: intelligenceEvents,
  companies,
  institutions: institutionCatalog,
  sectors,
  ipo: ipoCompanies,
  people,
  reports,
  sources,
  counts: {
    events: intelligenceEvents.length,
    companies: companies.length,
    institutions: institutionCatalog.length,
    sectors: sectors.length,
    ipo: ipoCompanies.length,
    people: people.length,
    reports: reports.length,
    sources: sources.length,
  },
};

const targetDirectory = resolve("data/public");
await mkdir(targetDirectory, { recursive: true });
await writeFile(
  resolve(targetDirectory, "dashboard.json"),
  `${JSON.stringify(snapshot, null, 2)}\n`,
  "utf8",
);
console.log(`Exported public snapshot: ${JSON.stringify(snapshot.counts)}`);
