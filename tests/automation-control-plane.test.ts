import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";

const root = path.resolve(import.meta.dirname, "..");
const read = (relativePath: string) =>
  fs.readFileSync(path.join(root, relativePath), "utf8");

type Output = {
  path: string;
  shared?: boolean;
  public?: boolean;
};

type AutomationJob = {
  id: string;
  name: string;
  owner: string;
  workflow: string;
  trigger: string;
  dependencies: string[];
  inputs: string[];
  outputs: Output[];
  freshnessSlaHours: number;
  timeoutMinutes: number;
  retry: number;
  failurePolicy: string;
  qualityGate: string;
};

type Registry = {
  schemaVersion: number;
  pipelineVersion: string;
  publicObjectTypes: Array<{ id: string; label: string; route: string }>;
  jobs: AutomationJob[];
};

const registry = JSON.parse(read("config/automation_jobs.json")) as Registry;

test("automation registry defines the exact four public research objects", () => {
  assert.equal(registry.schemaVersion, 1);
  assert.ok(registry.pipelineVersion);
  assert.deepEqual(
    registry.publicObjectTypes,
    [
      { id: "technology", label: "核心技术", route: "/technologies" },
      { id: "track", label: "核心赛道", route: "/technology" },
      { id: "person", label: "核心人物", route: "/people" },
      { id: "company", label: "核心公司", route: "/companies" },
    ],
  );

  const header = read("components/site-header.tsx");
  const sitemap = read("app/sitemap.ts");
  for (const objectType of registry.publicObjectTypes) {
    assert.match(header, new RegExp(objectType.label, "u"));
    assert.match(header, new RegExp(`"${objectType.route}"`, "u"));
    assert.match(sitemap, new RegExp(`"${objectType.route}"`, "u"));
  }
});

test("automation jobs have unique identities, valid dependencies and auditable contracts", () => {
  const ids = new Set<string>();
  const outputOwners = new Map<string, Array<{ id: string; shared: boolean }>>();

  for (const job of registry.jobs) {
    assert.match(job.id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/u);
    assert.equal(ids.has(job.id), false, `duplicate job id: ${job.id}`);
    ids.add(job.id);

    for (const field of [
      job.name,
      job.owner,
      job.workflow,
      job.trigger,
      job.failurePolicy,
      job.qualityGate,
    ]) {
      assert.ok(field);
    }
    assert.equal(fs.existsSync(path.join(root, job.workflow)), true, job.workflow);
    assert.ok(job.freshnessSlaHours > 0);
    assert.ok(job.timeoutMinutes > 0);
    assert.ok(job.retry >= 0);
    assert.ok(Array.isArray(job.inputs));
    assert.ok(Array.isArray(job.outputs));

    for (const output of job.outputs) {
      const owners = outputOwners.get(output.path) ?? [];
      owners.push({ id: job.id, shared: output.shared === true });
      outputOwners.set(output.path, owners);
    }
  }

  for (const job of registry.jobs) {
    for (const dependency of job.dependencies) {
      assert.equal(ids.has(dependency), true, `${job.id} -> ${dependency}`);
    }
  }

  for (const [output, owners] of outputOwners) {
    if (owners.length > 1) {
      assert.equal(
        owners.every((owner) => owner.shared),
        true,
        `${output} has undeclared shared owners`,
      );
    }
  }

  const state = new Map<string, "visiting" | "done">();
  const byId = new Map(registry.jobs.map((job) => [job.id, job]));
  function visit(jobId: string): void {
    const marker = state.get(jobId);
    assert.notEqual(marker, "visiting", `dependency cycle at ${jobId}`);
    if (marker === "done") return;
    state.set(jobId, "visiting");
    for (const dependency of byId.get(jobId)?.dependencies ?? []) {
      visit(dependency);
    }
    state.set(jobId, "done");
  }
  for (const job of registry.jobs) visit(job.id);
});

test("Pages builds current lineage without mutating committed public inputs", () => {
  const packageJson = JSON.parse(read("package.json")) as {
    scripts: Record<string, string>;
  };
  assert.equal(
    packageJson.scripts["validate:pipeline"],
    "python3 tools/run_pipeline.py check",
  );
  assert.match(packageJson.scripts["build:pages"], /^npm run validate:pipeline/u);

  const pages = read(".github/workflows/pages.yml");
  assert.match(pages, /fetch-depth: 0/u);
  assert.match(
    pages,
    /run_pipeline\.py refresh[\s\S]*out\/data\/data_lineage\.json/u,
  );
  assert.match(
    pages,
    /run_pipeline\.py build-provenance[\s\S]*out\/build-provenance\.json/u,
  );
  assert.match(pages, /git diff --exit-code -- config public\/data/u);
});

test("README describes the current read-only four-object product scope", () => {
  const readme = read("README.md");
  for (const label of ["核心技术", "核心赛道", "核心人物", "核心公司"]) {
    assert.match(readme, new RegExp(label, "u"));
  }
  assert.match(readme, /automation_jobs\.json/u);
  assert.match(readme, /data_lineage\.json/u);
  assert.match(readme, /pipeline_health\.json/u);
  assert.match(readme, /只读/u);
  assert.doesNotMatch(readme, /七个核心频道/u);
  assert.doesNotMatch(readme, /GitHub Token/u);
  assert.doesNotMatch(readme, /Contents: Read and write/u);
});
