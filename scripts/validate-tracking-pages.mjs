import fs from "node:fs";
import path from "node:path";
import process from "node:process";

const root = process.cwd();
const configPath = path.join(root, "config", "user_tracking.json");
const checkOutput = process.argv.includes("--check-output");
const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const requiredPageMarkers = ["产业链结构", "关键研究变量", "主要风险", "最新公开事件"];

function fail(messages) {
  for (const message of messages) {
    console.error(`TRACKING_ROUTE_ERROR: ${message}`);
  }
  process.exit(1);
}

if (!fs.existsSync(configPath)) {
  fail([`missing configuration file: ${configPath}`]);
}

let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, "utf8"));
} catch (error) {
  fail([`invalid JSON in config/user_tracking.json: ${error.message}`]);
}

const tracks = Array.isArray(config.tracks) ? config.tracks : [];
const errors = [];
const slugOwners = new Map();
const nameOwners = new Map();

if (tracks.length === 0) {
  errors.push("tracks must contain at least one entry");
}

for (const [index, track] of tracks.entries()) {
  const position = `tracks[${index}]`;
  const name = typeof track?.name === "string" ? track.name.trim() : "";
  const slug = typeof track?.slug === "string" ? track.slug.trim() : "";

  if (!name) errors.push(`${position}.name is required`);
  if (!slug) errors.push(`${position}.slug is required`);
  if (slug && !slugPattern.test(slug)) {
    errors.push(
      `${position}.slug "${slug}" is not URL-safe; use lowercase ASCII letters, digits and hyphens only`,
    );
  }

  const nameKey = name.toLocaleLowerCase("zh-CN");
  if (nameKey) {
    if (nameOwners.has(nameKey)) {
      errors.push(
        `duplicate track name "${name}" at indexes ${nameOwners.get(nameKey)} and ${index}`,
      );
    } else {
      nameOwners.set(nameKey, index);
    }
  }

  if (slug) {
    if (slugOwners.has(slug)) {
      errors.push(
        `duplicate track slug "${slug}" at indexes ${slugOwners.get(slug)} and ${index}`,
      );
    } else {
      slugOwners.set(slug, index);
    }
  }
}

const enabledTracks = tracks.filter((track) => track?.enabled !== false);
if (enabledTracks.length === 0) {
  errors.push("at least one track must be enabled");
}

if (errors.length) fail(errors);

if (!checkOutput) {
  console.log(
    `Tracking configuration valid: ${tracks.length} unique tracks, ${enabledTracks.length} enabled.`,
  );
  for (const track of enabledTracks) {
    console.log(`  /technology/${track.slug}/  <- ${track.name}`);
  }
  process.exit(0);
}

const outputErrors = [];
const routes = [];
for (const track of enabledTracks) {
  const relativePage = path.join("technology", track.slug, "index.html");
  const absolutePage = path.join(root, "out", relativePage);
  if (!fs.existsSync(absolutePage)) {
    outputErrors.push(`${track.name}: missing out/${relativePage}`);
    continue;
  }

  const html = fs.readFileSync(absolutePage, "utf8");
  const markers = [track.name, ...requiredPageMarkers];
  for (const marker of markers) {
    if (!html.includes(marker)) {
      outputErrors.push(
        `${track.name}: out/${relativePage} is missing generated content marker "${marker}"`,
      );
    }
  }
  if (/\b(?:undefined|null)\b/.test(html)) {
    outputErrors.push(
      `${track.name}: out/${relativePage} contains an undefined/null rendering artifact`,
    );
  }

  routes.push({
    name: track.name,
    slug: track.slug,
    route: `/technology/${track.slug}/`,
    file: `out/${relativePage}`,
  });
}

if (outputErrors.length) {
  fail([
    "Next.js did not export complete pages for every enabled technology track",
    ...outputErrors,
  ]);
}

const listingPath = path.join(root, "out", "technology", "index.html");
if (!fs.existsSync(listingPath)) {
  fail(["missing technology listing page: out/technology/index.html"]);
}

const manifestPath = path.join(root, "out", "technology", "route-manifest.json");
fs.writeFileSync(
  manifestPath,
  `${JSON.stringify(
    {
      generatedAt: new Date().toISOString(),
      trackCount: routes.length,
      routes,
    },
    null,
    2,
  )}\n`,
  "utf8",
);

console.log(
  `Verified ${routes.length} generated technology detail pages with complete structured content.`,
);
console.log("Route manifest written to out/technology/route-manifest.json.");
