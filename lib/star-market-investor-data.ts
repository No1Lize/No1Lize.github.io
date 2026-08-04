import rawSnapshot from "@/public/data/star_market_investors.json";
import {
  institutionDirectory,
  type InstitutionDirectoryEntry,
} from "@/lib/institution-ranking-data";
import {
  deriveStarInvestorReview,
  starInvestorReviewLabels,
  starInvestorReviewReasonLabels,
  type StarInvestorReviewStatus,
} from "@/lib/star-market-investor-review";

export {
  deriveStarInvestorReview,
  starInvestorReviewLabels,
  starInvestorReviewReasonLabels,
};
export type { StarInvestorReviewStatus };

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
  normalizedName: string;
  institutional: true;
  investorType: string;
  sourcePage: number;
  sourceSection: string;
  evidence: string;
  preIpoShares?: number;
  preIpoOwnershipPct?: number;
  publicContact?: StarMarketInvestorContact;
  contactStatus:
    | "prospectus-public"
    | "not-disclosed-in-prospectus"
    | "withheld-pending-review";
  reviewKey?: string;
  reviewStatus?: StarInvestorReviewStatus;
  reviewReasons?: string[];
  reviewedBy?: string;
  reviewedAt?: string;
  reviewNote?: string;
  reviewSource?: "manifest";
};

export type ReviewedStarMarketInvestor = StarMarketInvestor & {
  reviewStatus: StarInvestorReviewStatus;
  reviewReasons: string[];
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
  issuerInvestorRelations?: Partial<StarMarketInvestorContact>;
  institutionalInvestorCount: number;
  reviewCandidateCount?: number;
  verifiedInvestorCount?: number;
  rejectedInvestorCount?: number;
  naturalPersonContactsPublished: false;
  investors: StarMarketInvestor[];
  errors: string[];
};

type StarMarketInvestorSnapshot = {
  schemaVersion: number;
  generatedAt: string;
  companyCount: number;
  investorCount: number;
  reviewCandidateCount?: number;
  verifiedInvestorCount?: number;
  needsReviewInvestorCount?: number;
  rejectedInvestorCount?: number;
  reviewManifestDecisionCount?: number;
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
    holdingBinding?: string;
    reviewGate?: string;
    humanReview?: string;
    contactPublication?: string;
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
  investor: ReviewedStarMarketInvestor;
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
export const starMarketInvestorReviewManifestDecisionCount =
  snapshot.reviewManifestDecisionCount ?? 0;

export const starMarketInvestorCompanies = Object.values(snapshot.companies ?? {}).sort(
  (left, right) =>
    left.sector.localeCompare(right.sector, "zh-CN") ||
    left.ticker.localeCompare(right.ticker),
);

const reviewRank: Record<StarInvestorReviewStatus, number> = {
  verified: 2,
  needs_review: 1,
  rejected: 0,
};

export const starMarketInvestorAllRecords: StarMarketInvestorRecord[] =
  starMarketInvestorCompanies
    .flatMap((company) =>
      company.investors.map((rawInvestor) => {
        const review = deriveStarInvestorReview({
          ...rawInvestor,
          companyName: company.name,
        });
        const contactVerified =
          review.reviewStatus === "verified" &&
          rawInvestor.reviewSource === "manifest" &&
          rawInvestor.contactStatus === "prospectus-public" &&
          Boolean(rawInvestor.publicContact);
        const investor: ReviewedStarMarketInvestor = {
          ...rawInvestor,
          ...review,
          publicContact: contactVerified ? rawInvestor.publicContact : undefined,
          contactStatus: contactVerified
            ? "prospectus-public"
            : rawInvestor.contactStatus === "not-disclosed-in-prospectus"
              ? "not-disclosed-in-prospectus"
              : "withheld-pending-review",
        };
        return {
          company,
          investor,
          directoryInstitution: resolveStarInvestorInstitution(investor),
        };
      }),
    )
    .sort((left, right) => {
      const reviewOrder =
        reviewRank[right.investor.reviewStatus] -
        reviewRank[left.investor.reviewStatus];
      if (reviewOrder) return reviewOrder;
      return (
        left.company.name.localeCompare(right.company.name, "zh-CN") ||
        left.investor.name.localeCompare(right.investor.name, "zh-CN")
      );
    });

export const starMarketInvestorRecords = starMarketInvestorAllRecords.filter(
  (record) => record.investor.reviewStatus !== "rejected",
);

export const starMarketInvestorStats = {
  companies: starMarketInvestorCompanies.length,
  extracted: starMarketInvestorAllRecords.length,
  investors: starMarketInvestorRecords.length,
  verified: starMarketInvestorAllRecords.filter(
    (record) => record.investor.reviewStatus === "verified",
  ).length,
  needsReview: starMarketInvestorAllRecords.filter(
    (record) => record.investor.reviewStatus === "needs_review",
  ).length,
  rejected: starMarketInvestorAllRecords.filter(
    (record) => record.investor.reviewStatus === "rejected",
  ).length,
  linkedInstitutions: new Set(
    starMarketInvestorRecords
      .map((record) => record.directoryInstitution?.name)
      .filter(Boolean),
  ).size,
  publicContacts: starMarketInvestorRecords.filter(
    (record) => record.investor.contactStatus === "prospectus-public",
  ).length,
  reviewed: starMarketInvestorAllRecords.filter(
    (record) => record.investor.reviewSource === "manifest",
  ).length,
};
