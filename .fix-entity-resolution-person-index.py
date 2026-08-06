from pathlib import Path

path = Path("lib/entity-resolution.ts")
text = path.read_text(encoding="utf-8")
text = text.replace(
    'import { people } from "@/lib/catalog-data";',
    'import { people as catalogPeople } from "@/lib/catalog-data";',
)
old = '''const personIndex = new Map<string, typeof people>();
for (const person of people) {
  for (const alias of [person.name, person.englishName, person.slug]) {
    addIndex(personIndex, alias, person);
  }
}
'''
new = '''type ResolutionPerson = {
  slug: string;
  name: string;
  englishName?: string;
  aliases?: string[];
};

function configuredPersonName(raw: string) {
  const value = text(raw, 160);
  const base = text(value.replace(/\\s+@[A-Za-z0-9_]+$/u, ""), 160);
  if (!base || base.startsWith("The ")) return "";
  if (/[\\u3400-\\u9fff]/u.test(base)) {
    return /^[\\u3400-\\u9fff·•]{2,8}$/u.test(base) ? base : "";
  }
  const parts = base.split(/\\s+/u);
  if (parts.length < 2 || parts.length > 5) return "";
  return parts.every((part) => /^[A-Z][a-z]+(?:[-'][A-Z]?[a-z]+)*$/u.test(part))
    ? base
    : "";
}

const personIndex = new Map<string, ResolutionPerson[]>();
for (const person of catalogPeople) {
  for (const alias of [person.name, person.englishName, person.slug]) {
    addIndex(personIndex, alias, person);
  }
}
for (const track of userTrackingConfig.tracks) {
  for (const rawName of track.people) {
    const canonicalName = configuredPersonName(rawName);
    const key = normalizeEntityResolutionIdentity(canonicalName);
    if (!canonicalName || !key || personIndex.has(key)) continue;
    const person: ResolutionPerson = {
      slug: key,
      name: canonicalName,
      englishName: canonicalName,
      aliases: [rawName],
    };
    for (const alias of [canonicalName, rawName]) {
      addIndex(personIndex, alias, person);
    }
  }
}
'''
if text.count(old) != 1:
    raise SystemExit(f"expected person index block once, found {text.count(old)}")
text = text.replace(old, new)
path.write_text(text, encoding="utf-8")

path = Path("tools/entity_resolution.py")
text = path.read_text(encoding="utf-8")
old = '''        for alias in [person.get("name"), person.get("englishName"), person.get("slug")]:
            _add_index(index, alias, person)
'''
new = '''        for alias in [
            person.get("name"),
            person.get("englishName"),
            person.get("slug"),
            *(person.get("aliases", []) if isinstance(person.get("aliases"), list) else []),
        ]:
            _add_index(index, alias, person)
'''
if text.count(old) != 1:
    raise SystemExit(f"expected Python person index block once, found {text.count(old)}")
text = text.replace(old, new)
path.write_text(text, encoding="utf-8")
