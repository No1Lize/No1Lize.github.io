import assert from "node:assert/strict";
import test from "node:test";

import {
  companyProfileRefreshQueue,
  formatCompanyProfileQueueTime,
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

test("queue timestamps use a stable Taipei display or the empty fallback", () => {
  assert.equal(formatCompanyProfileQueueTime(""), "尚无");
  assert.match(
    formatCompanyProfileQueueTime("2026-08-03T13:35:00Z"),
    /08.*03.*21.*35/u,
  );
});
