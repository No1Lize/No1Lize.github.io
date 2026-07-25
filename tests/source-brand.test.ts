import assert from "node:assert/strict";
import test from "node:test";

import { sourceBrandKey, sourceHostname } from "../lib/source-brand";

test("normalizes source hosts", () => {
  assert.equal(sourceHostname("https://www.finance.yahoo.com/news"), "finance.yahoo.com");
  assert.equal(sourceHostname("https://ir.ionq.com/news"), "ir.ionq.com");
});

test("collapses Yahoo regional and editorial sites into one brand", () => {
  const values = [
    "https://tw.yahoo.com/?p=us",
    "https://finance.yahoo.com/",
    "https://news.yahoo.com/",
    "https://s.yimg.com/",
  ];
  assert.deepEqual(new Set(values.map(sourceBrandKey)), new Set(["yahoo"]));
});

test("collapses ordinary subdomains to the registrable brand domain", () => {
  assert.equal(sourceBrandKey("https://ir.ionq.com/news"), "ionq.com");
  assert.equal(sourceBrandKey("https://news.google.co.uk/"), "google.co.uk");
  assert.notEqual(sourceBrandKey("https://reuters.com/"), sourceBrandKey("https://bloomberg.com/"));
});
