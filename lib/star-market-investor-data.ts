import rawSnapshot from "@/public/data/star_market_investors.json";
import {
  institutionDirectory,
  type InstitutionDirectoryEntry,
} from "@/lib/institution-ranking-data";

export type StarMarketInvestorContact = {
  officeAddress?: string;
  phone?: string;
  email?: string;
  website?: string;
  sourcePage: number;
  scope: string;
};

export type StarMarketInvestor = {
  id: string;
  name: string;
  disclosedName?: string;
  normalizedName: string;
  institutional: true;
  investorType: string;
  sourcePage: number;
  sourceSection: string;
  evidence: string;
  preIpoShares: number;
  preIpoOwnershipPct: number;
  nameResolution: "definitions" | "basic-information";
  definitionSourcePage?: number;
  publicContact?: StarMarketInvestorContact;
  contactStatus: "prospectus-public" | "not-disclosed-in-prospectus";
};

export type StarMarketCompanyInvestorProfile = {
  slug: string;
  name: string;
  ticker: string;
  exchange: string;
  sector: string;
  updatedAt: string;
  status: "ok" | "partial" | "retained";
  prospectus: {
    title: string;
    url: string;
    publishedAt: string;
    announcementId: string;
    pageCount: number;
    textPageCount: number;
    sha256: string;
    provider: string;
  };
  issuerInvestorRelations?: StarMarketInvestorContact;
  institutionalInvestorCount: number;
  naturalPersonContactsPublished: false;
  investors: StarMarketInvestor[];
  errors: string[];
};

type StarMarketInvestorSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  companyCount: number;
  investorCount: number;
  scope: {
    market: string;
    listingRule: string;
    shareholderRule: string;
  };
  privacy: {
    naturalPersonShareholdersExcluded: boolean;
    personalPhonesExcluded: boolean;
    identityNumbersExcluded: boolean;
    contacts: string;
  };
  methodology: {
    prospectusProvider: string;
    pdfExtraction: string;
    shareholderEvidence?: string;
    nameResolution?: string;
    contactEvidence?: string;
    retention: string;
  };
  companies: Record<string, StarMarketCompanyInvestorProfile>;
  sourceStatus: {
    id: string;
    companySlug: string;
    ticker: string;
    status: string;
    investorCount: number;
    retainedPrevious: boolean;
    durationMs: number;
    errors: string[];
  }[];
};

export type StarMarketInvestorRecord = {
  company: StarMarketCompanyInvestorProfile;
  investor: StarMarketInvestor;
  directoryInstitution?: InstitutionDirectoryEntry;
};

const snapshot = rawSnapshot as StarMarketInvestorSnapshot;

export function normalizeStarInvestorName(value: string): string {
  return value
    .normalize("NFKC")
    .toLocaleLowerCase("zh-CN")
    .replace(/[\s·•・()（）\[\]【】{}<>《》,，.。:：;；'"“”‘’_\-/\\&+－—]/gu, "")
    .trim();
}

function institutionIdentityTerms(entry: InstitutionDirectoryEntry): string[] {
  return [entry.name, entry.fullName ?? ""]
    .map(normalizeStarInvestorName)
    .filter(Boolean);
}

export function resolveStarInvestorInstitution(
  investor: Pick<StarMarketInvestor, "name" | "normalizedName">,
): InstitutionDirectoryEntry | undefined {
  const investorKey = investor.normalizedName || normalizeStarInvestorName(investor.name);
  if (!investorKey) return undefined;
  return institutionDirectory.find((entry) =>
    institutionIdentityTerms(entry).some((term) => {
      if (term === investorKey) return true;
      if (term.length < 4 || investorKey.length < 4) return false;
      return term.includes(investorKey) || investorKey.includes(term);
    }),
  );
}

export function starInvestorInstitutionHref(
  record: StarMarketInvestorRecord,
): string {
  const institution = record.directoryInstitution;
  if (institution?.profileSlug) return `/institutions/${institution.profileSlug}`;
  const query = institution?.name ?? record.investor.name;
  return `/institutions?institution=${encodeURIComponent(query)}`;
}

export const starMarketInvestorGeneratedAt = snapshot.generatedAt || "";
export const starMarketInvestorScope = snapshot.scope;
export const starMarketInvestorPrivacy = snapshot.privacy;
export const starMarketInvestorMethodology = snapshot.methodology;

export const starMarketInvestorCompanies = Object.values(snapshot.companies ?? {}).sort(
  (left, right) =>
    left.sector.localeCompare(right.sector, "zh-CN") ||
    left.ticker.localeCompare(right.ticker),
);

export const starMarketInvestorRecords: StarMarketInvestorRecord[] =
  starMarketInvestorCompanies
    .flatMap((company) =>
      company.investors.map((investor) => ({
        company,
        investor,
        directoryInstitution: resolveStarInvestorInstitution(investor),
      })),
    )
    .sort(
      (left, right) =>
        right.investor.preIpoOwnershipPct -
          left.investor.preIpoOwnershipPct ||
        left.company.sector.localeCompare(right.company.sector, "zh-CN") ||
        left.investor.name.localeCompare(right.investor.name, "zh-CN"),
    );

export const starMarketInvestorStats = {
  companies: starMarketInvestorCompanies.length,
  investors: starMarketInvestorRecords.length,
  linkedInstitutions: starMarketInvestorRecords.filter(
    (record) => Boolean(record.directoryInstitution),
  ).length,
  prospectusContacts: starMarketInvestorRecords.filter(
    (record) => record.investor.contactStatus === "prospectus-public",
  ).length,
  sectors: new Set(starMarketInvestorCompanies.map((company) => company.sector)).size,
};

export function getStarMarketInvestorCompany(
  slug: string,
): StarMarketCompanyInvestorProfile | undefined {
  return snapshot.companies?.[slug];
}
