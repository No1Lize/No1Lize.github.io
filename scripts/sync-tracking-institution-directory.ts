import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { institutionDirectory } from "../lib/institution-ranking-data";

type Track = {
  slug?: string;
  name?: string;
  enabled?: boolean;
  keywords?: string[];
  people?: string[];
  sampleCompanies?: string[];
  ignoredRecommendations?: {
    companies?: string[];
    people?: string[];
  };
};

type TrackingConfig = {
  tracks?: Track[];
};

type LedgerRow = {
  track?: string;
  kind?: string;
  value?: string;
  addedAt?: string;
  removedAt?: string;
  evidence?: string[];
};

type DiscoveryLedger = {
  schemaVersion?: number;
  updatedAt?: string;
  tracks?: Record<string, Record<string, string>>;
  added?: LedgerRow[];
  removed?: LedgerRow[];
};

type InstitutionTeamMember = {
  name?: string;
  role?: string;
};

type VentureSnapshot = {
  institutions?: Record<string, { team?: InstitutionTeamMember[] }>;
};

const ROOT = resolve(fileURLToPath(new URL("..", import.meta.url)));
const CONFIG_PATH = resolve(ROOT, "config/user_tracking.json");
const LEDGER_PATH = resolve(ROOT, "config/tracking_auto_discovery.json");
const VENTURE_PATH = resolve(ROOT, "public/data/venture_profiles.json");

const INVESTMENT_ROLE_RE =
  /创始合伙|联合创始|共同创始|管理合伙|主管合伙|普通合伙|投资合伙|合伙人|董事总经理|投资负责人|投资总监|创始人|董事长|首席执行|founding\s+partner|co[-\s]?founder|managing\s+partner|general\s+partner|venture\s+partner|\bpartner\b|managing\s+director|head\s+of\s+invest|founder|chair(?:man|woman|person)?|\bceo\b/iu;

function nowIso(): string {
  return new Date().toISOString().replace(".000Z", "+00:00");
}

function normalize(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[^a-z0-9\u3400-\u9fff]+/gu, "");
}

function personBase(value: unknown): string {
  return String(value ?? "")
    .normalize("NFKC")
    .replace(/\s+@[A-Za-z0-9_]{1,15}$/u, "")
    .replace(/\s+/gu, " ")
    .trim();
}

function personKey(value: unknown): string {
  return normalize(personBase(value));
}

function isInvestmentTrack(track: Track): boolean {
  const name = normalize(track.name);
  if (name === normalize("风险投资") || name === normalize("venture capital")) return true;
  const keywords = new Set((track.keywords ?? []).map(normalize));
  return keywords.has(normalize("私人股权投资")) && keywords.has(normalize("天使轮"));
}

function isLikelyPersonName(value: unknown): boolean {
  const name = personBase(value);
  if (!name || name.length > 80 || /https?:\/\/|\d/u.test(name)) return false;
  if (/公司|集团|基金|资本|团队|研究院|委员会|press|team|management|leadership/iu.test(name)) {
    return false;
  }
  if (/^[\u3400-\u9fff·]{2,8}$/u.test(name)) {
    return name.replace(/·/gu, "").length <= 5;
  }
  const words = name.split(" ");
  return words.length >= 2 && words.length <= 5 && words.every((word) => /^[A-Za-z][A-Za-z'.-]*$/u.test(word));
}

function verifiedInstitutionPeople(snapshot: VentureSnapshot): Set<string> {
  const people = new Set<string>();
  for (const profile of Object.values(snapshot.institutions ?? {})) {
    for (const member of profile.team ?? []) {
      const name = personBase(member.name);
      const role = String(member.role ?? "").trim();
      if (name && INVESTMENT_ROLE_RE.test(role) && isLikelyPersonName(name)) {
        people.add(personKey(name));
      }
    }
  }
  return people;
}

function ensureLedger(ledger: DiscoveryLedger): Required<DiscoveryLedger> {
  return {
    schemaVersion: ledger.schemaVersion ?? 1,
    updatedAt: ledger.updatedAt ?? "",
    tracks: ledger.tracks ?? {},
    added: ledger.added ?? [],
    removed: ledger.removed ?? [],
  };
}

function rowKey(row: LedgerRow): string {
  return `${row.track ?? ""}|${row.kind ?? ""}|${normalize(row.value)}`;
}

function addLedgerEntry(
  ledger: Required<DiscoveryLedger>,
  trackSlug: string,
  kind: string,
  value: string,
  evidence: string[],
  stamp: string,
): void {
  const key = `${trackSlug}|${kind}|${normalize(value)}`;
  const existing = ledger.added.find((row) => rowKey(row) === key);
  if (existing) {
    existing.evidence = [...new Set([...(existing.evidence ?? []), ...evidence])].sort();
    return;
  }
  ledger.added.push({ track: trackSlug, kind, value, addedAt: stamp, evidence: [...new Set(evidence)].sort() });
}

function removeAutoRow(
  ledger: Required<DiscoveryLedger>,
  row: LedgerRow,
  stamp: string,
): void {
  const key = rowKey(row);
  ledger.added = ledger.added.filter((candidate) => rowKey(candidate) !== key);
  if (!ledger.removed.some((candidate) => rowKey(candidate) === key)) {
    ledger.removed.push({
      track: row.track,
      kind: row.kind,
      value: row.value,
      removedAt: stamp,
    });
  }
}

type TrackSyncSummary = {
  track: string;
  addedInstitutions: string[];
  prunedUnverifiedPeople: string[];
  sampleInstitutionCount: number;
  eligibleInstitutionCount: number;
  blockedInstitutionCount: number;
};

export function syncInstitutionDirectory(
  config: TrackingConfig,
  rawLedger: DiscoveryLedger,
  ventureSnapshot: VentureSnapshot,
): {
  changed: boolean;
  directoryCount: number;
  tracks: TrackSyncSummary[];
  ledger: Required<DiscoveryLedger>;
} {
  const ledger = ensureLedger(rawLedger);
  const stamp = nowIso();
  const directoryNames = institutionDirectory.map((entry) => entry.name);
  const directoryAliasSets = institutionDirectory.map((entry) => ({
    name: entry.name,
    keys: new Set([entry.name, entry.fullName].filter(Boolean).map(normalize)),
  }));
  const verifiedPeople = verifiedInstitutionPeople(ventureSnapshot);
  const summaries: TrackSyncSummary[] = [];
  let changed = false;

  for (const track of config.tracks ?? []) {
    if (!track.enabled || !isInvestmentTrack(track)) continue;
    const slug = String(track.slug ?? "");
    const samples = track.sampleCompanies ?? (track.sampleCompanies = []);
    const people = track.people ?? (track.people = []);
    const blocked = new Set(
      ledger.removed
        .filter((row) => row.track === slug && row.kind === "sampleCompanies")
        .map((row) => normalize(row.value)),
    );
    for (const value of track.ignoredRecommendations?.companies ?? []) blocked.add(normalize(value));

    // Owner-deleted automatic entries are tombstones and must never be silently
    // restored. Completeness therefore means every non-tombstoned directory
    // institution is referenced, not that blocked entries are reintroduced.
    const eligibleDirectoryEntries = directoryAliasSets.filter(
      (entry) => ![...entry.keys].some((key) => blocked.has(key)),
    );

    const existingKeys = new Set(samples.map(normalize));
    const addedInstitutions: string[] = [];
    for (const entry of eligibleDirectoryEntries) {
      if ([...entry.keys].some((key) => existingKeys.has(key))) continue;
      samples.push(entry.name);
      for (const key of entry.keys) existingKeys.add(key);
      addedInstitutions.push(entry.name);
      addLedgerEntry(
        ledger,
        slug,
        "sampleCompanies",
        entry.name,
        ["investment-institution-directory", "shared-directory-reference"],
        stamp,
      );
      changed = true;
    }

    const autoPeopleRows = ledger.added.filter(
      (row) => row.track === slug && row.kind === "people",
    );
    const unverifiedKeys = new Map<string, LedgerRow>();
    for (const row of autoPeopleRows) {
      const key = personKey(row.value);
      if (key && !verifiedPeople.has(key)) unverifiedKeys.set(key, row);
    }
    const prunedUnverifiedPeople: string[] = [];
    if (unverifiedKeys.size) {
      track.people = people.filter((value) => {
        const key = personKey(value);
        const row = unverifiedKeys.get(key);
        if (!row) return true;
        prunedUnverifiedPeople.push(value);
        removeAutoRow(ledger, row, stamp);
        changed = true;
        return false;
      });
    }

    const referencedCount = directoryAliasSets.filter((entry) =>
      [...entry.keys].some((key) => existingKeys.has(key)),
    ).length;
    const eligibleReferencedCount = eligibleDirectoryEntries.filter((entry) =>
      [...entry.keys].some((key) => existingKeys.has(key)),
    ).length;
    if (eligibleReferencedCount !== eligibleDirectoryEntries.length) {
      throw new Error(
        `风险投资赛道仅引用 ${eligibleReferencedCount}/${eligibleDirectoryEntries.length} 家未屏蔽投资机构，拒绝写入不完整同步。`,
      );
    }
    const blockedInstitutionCount = directoryAliasSets.length - eligibleDirectoryEntries.length;
    ledger.tracks[slug] = {
      ...(ledger.tracks[slug] ?? {}),
      lastInstitutionDirectorySyncAt: stamp,
      institutionDirectoryCount: String(directoryNames.length),
      eligibleInstitutionDirectoryCount: String(eligibleDirectoryEntries.length),
      blockedInstitutionDirectoryCount: String(blockedInstitutionCount),
    };
    summaries.push({
      track: slug,
      addedInstitutions,
      prunedUnverifiedPeople,
      sampleInstitutionCount: referencedCount,
      eligibleInstitutionCount: eligibleDirectoryEntries.length,
      blockedInstitutionCount,
    });
  }

  if (changed) ledger.updatedAt = stamp;
  return { changed, directoryCount: directoryNames.length, tracks: summaries, ledger };
}

function run(): void {
  const dryRun = process.argv.includes("--dry-run");
  const config = JSON.parse(readFileSync(CONFIG_PATH, "utf8")) as TrackingConfig;
  const ledger = JSON.parse(readFileSync(LEDGER_PATH, "utf8")) as DiscoveryLedger;
  const venture = JSON.parse(readFileSync(VENTURE_PATH, "utf8")) as VentureSnapshot;
  const result = syncInstitutionDirectory(config, ledger, venture);
  if (!dryRun && result.changed) {
    writeFileSync(CONFIG_PATH, `${JSON.stringify(config, null, 2)}\n`, "utf8");
    writeFileSync(LEDGER_PATH, `${JSON.stringify(result.ledger, null, 2)}\n`, "utf8");
  }
  process.stdout.write(`${JSON.stringify({
    changed: result.changed,
    directoryCount: result.directoryCount,
    tracks: result.tracks,
  })}\n`);
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  run();
}
