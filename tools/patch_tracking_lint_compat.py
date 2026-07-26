#!/usr/bin/env python3
"""Apply minimal React lint compatibility fixes to tracking components."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN = ROOT / "components" / "tracking-admin-module-recommendations.tsx"
BRIDGE = ROOT / "components" / "tracking-recommendations-bridge.tsx"
PANEL = ROOT / "components" / "user-tracking-panel.tsx"


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        print(f"{label}: already applied")
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected one source block, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"{label}: applied")


def patch_admin() -> None:
    replace_once(
        ADMIN,
        'import { useEffect, useMemo, useState } from "react";\n',
        'import { useEffect, useMemo, useState, useSyncExternalStore } from "react";\n',
        "admin hydration import",
    )
    replace_once(
        ADMIN,
        '''const LISTED_TITLE = "上市公司关注管理";
const SOURCE_TITLE = "补充信息源";
''',
        '''const LISTED_TITLE = "上市公司关注管理";
const SOURCE_TITLE = "补充信息源";
const subscribeToHydration = () => () => undefined;
const getClientHydrationSnapshot = () => true;
const getServerHydrationSnapshot = () => false;
''',
        "admin hydration store",
    )
    replace_once(
        ADMIN,
        '''  const { articles } = useArticles();
  const [mounted, setMounted] = useState(false);
  const [dismissalVersion, setDismissalVersion] = useState(0);
''',
        '''  const { articles } = useArticles();
  const mounted = useSyncExternalStore(
    subscribeToHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const [dismissalVersion, setDismissalVersion] = useState(0);
''',
        "admin mounted state",
    )
    replace_once(
        ADMIN,
        '''  useEffect(() => {
    setMounted(true);
    let frame = 0;
''',
        '''  useEffect(() => {
    let frame = 0;
''',
        "admin effect state update",
    )
    replace_once(
        ADMIN,
        '''  const listedRecommendations = useMemo(() => {
    if (!snapshot.sector) return [];
''',
        '''  const listedRecommendations = useMemo(() => {
    void dismissalVersion;
    if (!snapshot.sector) return [];
''',
        "admin listed dismissal dependency",
    )
    replace_once(
        ADMIN,
        '''  const sourceRecommendations = useMemo(() => {
    if (!snapshot.sector) return [];
''',
        '''  const sourceRecommendations = useMemo(() => {
    void dismissalVersion;
    if (!snapshot.sector) return [];
''',
        "admin source dismissal dependency",
    )


def patch_bridge() -> None:
    replace_once(
        BRIDGE,
        'import { useEffect, useMemo, useState } from "react";\n',
        'import { useEffect, useMemo, useState, useSyncExternalStore } from "react";\n',
        "bridge hydration import",
    )
    replace_once(
        BRIDGE,
        '''const LIST_FIELD_META = {
''',
        '''const subscribeToHydration = () => () => undefined;
const getClientHydrationSnapshot = () => true;
const getServerHydrationSnapshot = () => false;

const LIST_FIELD_META = {
''',
        "bridge hydration store",
    )
    replace_once(
        BRIDGE,
        '''  const { articles } = useArticles();
  const [mounted, setMounted] = useState(false);
  const [dismissalVersion, setDismissalVersion] = useState(0);
''',
        '''  const { articles } = useArticles();
  const mounted = useSyncExternalStore(
    subscribeToHydration,
    getClientHydrationSnapshot,
    getServerHydrationSnapshot,
  );
  const [dismissalVersion, setDismissalVersion] = useState(0);
''',
        "bridge mounted state",
    )
    replace_once(
        BRIDGE,
        '''  useEffect(() => {
    setMounted(true);
    let frame = 0;
''',
        '''  useEffect(() => {
    let frame = 0;
''',
        "bridge effect state update",
    )
    replace_once(
        BRIDGE,
        '''  const recommendations = useMemo(() => {
    if (!snapshot.sector) return EMPTY_RECOMMENDATIONS;
''',
        '''  const recommendations = useMemo(() => {
    void dismissalVersion;
    if (!snapshot.sector) return EMPTY_RECOMMENDATIONS;
''',
        "bridge dismissal dependency",
    )


def patch_panel() -> None:
    replace_once(
        PANEL,
        'import { useEffect, useMemo, useRef, useState } from "react";\n',
        'import { useMemo, useRef, useState } from "react";\n',
        "panel effect import",
    )
    replace_once(
        PANEL,
        '''  const track = config.tracks[active];
  const connected = Boolean(username && remoteSha);
''',
        '''  const activeIndex = Math.min(
    active,
    Math.max(0, config.tracks.length - 1),
  );
  const track = config.tracks[activeIndex];
  const connected = Boolean(username && remoteSha);
''',
        "panel safe active index",
    )
    replace_once(
        PANEL,
        '''  useEffect(() => {
    if (active >= config.tracks.length) {
      setActive(Math.max(0, config.tracks.length - 1));
    }
  }, [active, config.tracks.length]);

''',
        '',
        "panel state-normalizing effect",
    )
    replace_once(
        PANEL,
        '''  function removeTrack(): void {
    if (!track) return;
    update({
      ...config,
      tracks: config.tracks.filter((_, index) => index !== active),
      listedCompanies: config.listedCompanies.map((company) =>
        company.sector === track.name
          ? { ...company, sector: "未分类" }
          : company,
      ),
      sources: config.sources.map((source) =>
        source.sector === track.name
          ? { ...source, sector: "未分类" }
          : source,
      ),
    });
  }
''',
        '''  function removeTrack(): void {
    if (!track) return;
    const nextTracks = config.tracks.filter(
      (_, index) => index !== activeIndex,
    );
    update({
      ...config,
      tracks: nextTracks,
      listedCompanies: config.listedCompanies.map((company) =>
        company.sector === track.name
          ? { ...company, sector: "未分类" }
          : company,
      ),
      sources: config.sources.map((source) =>
        source.sector === track.name
          ? { ...source, sector: "未分类" }
          : source,
      ),
    });
    setActive(Math.min(activeIndex, Math.max(0, nextTracks.length - 1)));
  }
''',
        "panel track removal",
    )
    replacements = (
        ("index === active ? { ...item, enabled: !item.enabled } : item", "index === activeIndex ? { ...item, enabled: !item.enabled } : item", "panel toggle index"),
        ("index === active\n          ? { ...item, [field]: [...item[field], value] }", "index === activeIndex\n          ? { ...item, [field]: [...item[field], value] }", "panel add-list index"),
        ("index === active\n          ? {", "index === activeIndex\n          ? {", "panel remove-list index"),
        ("data-active={index === active}", "data-active={index === activeIndex}", "panel active tab"),
    )
    for old, new, label in replacements:
        replace_once(PANEL, old, new, label)


def main() -> None:
    patch_admin()
    patch_bridge()
    patch_panel()


if __name__ == "__main__":
    main()
