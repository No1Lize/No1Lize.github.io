import type { MetadataRoute } from "next";
import { companies, institutionCatalog, ipoCompanies, people, reports } from "@/lib/catalog-data";
import { sectors } from "@/lib/intelligence-data";

export const dynamic = "force-static";

export default function sitemap(): MetadataRoute.Sitemap {
  const base = "https://no1lize.github.io";
  const paths = [
    "", "/technology", "/companies", "/institutions", "/ipo", "/reports", "/people", "/search",
    ...sectors.map((item) => `/technology/${item.slug}`),
    ...companies.map((item) => `/companies/${item.slug}`),
    ...institutionCatalog.map((item) => `/institutions/${item.slug}`),
    ...ipoCompanies.map((item) => `/ipo/${item.slug}`),
    ...reports.map((item) => `/reports/${item.slug}`),
    ...people.map((item) => `/people/${item.slug}`),
  ];
  return paths.map((path) => ({ url: `${base}${path}`, lastModified: new Date("2026-07-24"), changeFrequency: path ? "weekly" : "daily" }));
}
