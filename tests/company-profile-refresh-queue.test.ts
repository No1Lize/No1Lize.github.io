import assert from "node:assert/strict";
import test from "node:test";

import {
  companyProfileRefreshQueue,
  formatCompanyProfileQueueTime,
  normalizeCompanyProfileRefreshQueue,
} from "../lib/company-profile-refresh-queue";

test("company profile refresh queue stays within the ten-company execution cap", () => {
  assert.ok(companyProfileRefreshQueue.selectionLimit >= 0);
  assert.ok(companyProfileRefreshQueue.selectionLimit <= 10);
  assert.ok(companyProfileRefreshQueue.selectedCount <= 10);
  assert.equal(
    companyProfileRefreshQueue.selectedSlugs.length,
    companyProfileRefreshQueue.selectedCount,
  );
});

test("queue entries expose traceable high-signal evidence", () => {
  for (const entry of companyProfileRefreshQueue.entries) {
    assert.ok(entry.companySlug);
    assert.ok(entry.companyName);
    assert.ok(entry.priority > 0);
    assert.ok(entry.eventFingerprints.length > 0);
    assert.ok(entry.evidence.every((item) => item.sourceUrl.startsWith("http")));
  }
});

test("generated queues normalize heterogeneous event type maps", () => {
  const queue = normalizeCompanyProfileRefreshQueue({
    generatedAt: "2026-08-04T11:30:00Z",
    lookbackDays: 14,
    selectionLimit: 3,
    pendingCount: 2,
    selectedCount: 99,
    selectedSlugs: ["alpha", "beta", "beta", ""],
    entries: [
      {
        companySlug: "alpha",
        companyName: "Alpha",
        priority: 80,
        status: "selected",
        eventCount: 2,
        sourceCount: 1,
        eventTypes: { 商业进展: 2 },
        newestPublishedAt: "2026-08-04",
        reasons: ["商业进展"],
        eventFingerprints: ["alpha-event"],
        evidence: [
          {
            fingerprint: "alpha-event",
            articleId: "article-alpha",
            title: "Alpha update",
            eventType: "商业进展",
            publishedAt: "2026-08-04",
            importance: 4,
            priority: 80,
            sourceName: "Alpha",
            sourceUrl: "https://alpha.example/update",
            sourceLevel: "official",
          },
        ],
      },
      {
        companySlug: "beta",
        companyName: "Beta",
        priority: 60,
        status: "pending",
        eventCount: 1,
        sourceCount: 1,
        eventTypes: {
          产业投资: 1,
          invalid: undefined,
          negative: -2,
          text: "3",
        },
        newestPublishedAt: "2026-08-03",
        reasons: ["产业投资"],
        eventFingerprints: ["beta-event"],
        evidence: [
          {
            fingerprint: "beta-event",
            articleId: "article-beta",
            title: "Beta funding",
            eventType: "产业投资",
            publishedAt: "2026-08-03",
            importance: 3,
            priority: 60,
            sourceName: "Beta",
            sourceUrl: "https://beta.example/funding",
            sourceLevel: "official",
          },
        ],
      },
    ],
  });

  assert.equal(queue.selectedCount, 2);
  assert.deepEqual(queue.selectedSlugs, ["alpha", "beta"]);
  assert.deepEqual(queue.entries[0]?.eventTypes, { 商业进展: 2 });
  assert.deepEqual(queue.entries[1]?.eventTypes, {
    产业投资: 1,
    text: 3,
  });
});

test("malformed queue records are rejected at the frontend boundary", () => {
  const queue = normalizeCompanyProfileRefreshQueue({
    lookbackDays: "bad",
    selectionLimit: 100,
    selectedSlugs: ["safe", 123, null],
    entries: [
      {
        companySlug: "",
        companyName: "Missing slug",
        priority: 10,
      },
      {
        companySlug: "unsafe-source",
        companyName: "Unsafe source",
        priority: 10,
        eventTypes: { update: 1 },
        evidence: [
          {
            fingerprint: "unsafe",
            sourceUrl: "javascript:alert(1)",
          },
        ],
      },
    ],
  });

  assert.equal(queue.lookbackDays, 7);
  assert.equal(queue.selectionLimit, 10);
  assert.deepEqual(queue.selectedSlugs, ["safe"]);
  assert.equal(queue.entries.length, 1);
  assert.deepEqual(queue.entries[0]?.evidence, []);
});

test("queue timestamps use a stable Taipei display or the empty fallback", () => {
  assert.equal(formatCompanyProfileQueueTime(""), "尚无");
  assert.match(
    formatCompanyProfileQueueTime("2026-08-03T13:35:00Z"),
    /08.*03.*21.*35/u,
  );
});
