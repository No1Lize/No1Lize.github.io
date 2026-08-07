import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import test from "node:test";

const ROOT = process.cwd();

test("vendored PDF.js worker matches the installed pdfjs-dist version", () => {
  const packageJson = JSON.parse(
    readFileSync(path.join(ROOT, "package.json"), "utf8"),
  ) as { dependencies?: Record<string, string> };
  const version = packageJson.dependencies?.["pdfjs-dist"];

  assert.ok(version, "package.json must declare pdfjs-dist");
  assert.match(version, /^\d+\.\d+\.\d+$/);

  const worker = readFileSync(
    path.join(ROOT, "public", "vendor", "pdf.worker.min.mjs"),
    "utf8",
  );
  assert.ok(
    worker.includes(version),
    `vendored PDF.js worker must contain dependency version ${version}`,
  );
});
