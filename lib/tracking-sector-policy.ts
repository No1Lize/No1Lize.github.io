import entitySeedConfig from "../config/tracking_entity_seeds.json";

type EntitySeedConfig = {
  schemaVersion: number;
  seedAcronyms: string[];
  globalTerms: string[];
  sectorTerms: Record<string, string[]>;
};

const CONFIG = entitySeedConfig as EntitySeedConfig;

const SECTOR_ALIASES: Record<string, string> = {
  "ai": "ai / agi",
  "agi": "ai / agi",
  "ai/agi": "ai / agi",
  "ai / agi": "ai / agi",
  "人工智能": "ai / agi",
  "robot": "机器人",
  "robotics": "机器人",
  "机器人": "机器人",
  "具身智能": "机器人",
  "semiconductor": "半导体",
  "semiconductors": "半导体",
  "半导体": "半导体",
  "新能源": "新能源",
  "new energy": "新能源",
  "energy": "新能源",
  "biotech": "生物科技",
  "biotechnology": "生物科技",
  "生物科技": "生物科技",
  "量子计算": "量子计算",
  "quantum computing": "量子计算",
  "商业航天": "商业航天",
  "commercial space": "商业航天",
  "web3": "web3",
  "新材料": "新材料",
  "new materials": "新材料",
  "智能制造": "智能制造",
  "smart manufacturing": "智能制造",
  "可控核聚变": "可控核聚变",
  "核聚变": "可控核聚变",
  "fusion": "可控核聚变",
};

function normalize(value: string): string {
  return value
    .normalize("NFKC")
    .replace(/[／]/g, "/")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase("zh-CN");
}

export function canonicalTrackingSector(value: string): string {
  const normalized = normalize(value);
  return SECTOR_ALIASES[normalized] ?? normalized;
}

export function trackingSectorsMatch(articleSector: string, selectedSector: string): boolean {
  const article = canonicalTrackingSector(articleSector);
  const selected = canonicalTrackingSector(selectedSector);
  return Boolean(article && selected && article === selected);
}

const TERM_OWNERS = new Map<string, Set<string>>();
for (const [sector, terms] of Object.entries(CONFIG.sectorTerms)) {
  const canonicalSector = canonicalTrackingSector(sector);
  for (const term of terms) {
    const key = normalize(term);
    const owners = TERM_OWNERS.get(key) ?? new Set<string>();
    owners.add(canonicalSector);
    TERM_OWNERS.set(key, owners);
  }
}

export function trackingSectorSeedTerms(selectedSector: string): string[] {
  const canonical = canonicalTrackingSector(selectedSector);
  const terms = new Map<string, string>();
  for (const [sector, sectorTerms] of Object.entries(CONFIG.sectorTerms)) {
    if (canonicalTrackingSector(sector) !== canonical) continue;
    for (const term of sectorTerms) terms.set(normalize(term), term);
  }
  return [...terms.values()];
}

export function isKnownTrackingSeedTerm(value: string): boolean {
  const key = normalize(value);
  return TERM_OWNERS.has(key) || CONFIG.globalTerms.some((term) => normalize(term) === key);
}

export function isTrackingTermAllowedForSector(value: string, selectedSector: string): boolean {
  const owners = TERM_OWNERS.get(normalize(value));
  if (!owners?.size) return false;
  return owners.has(canonicalTrackingSector(selectedSector));
}
