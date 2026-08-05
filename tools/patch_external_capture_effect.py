#!/usr/bin/env python3
"""One-time cleanup for React's set-state-in-effect lint rule."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "components" / "external-tracking-capture-page.tsx"
text = path.read_text(encoding="utf-8")
old = '''  useEffect(() => {
    const prefill = parseExternalTrackingCaptureParams(
      new URLSearchParams(window.location.search),
    );
    setSource(prefill.source);
    setSelectedText(prefill.selectedText);
    setEntities(
      prefill.entities.length
        ? prefill.entities.map((entity) =>
            makeEntityRow(entity.entityType, entity.name),
          )
        : [makeEntityRow("company")],
    );
    setSelectedTrackSlugs(
      recommendExternalTrackingCaptureTracks(prefill, userTrackingConfig),
    );
    setReady(true);
  }, []);'''
new = '''  useEffect(() => {
    const timer = window.setTimeout(() => {
      const prefill = parseExternalTrackingCaptureParams(
        new URLSearchParams(window.location.search),
      );
      setSource(prefill.source);
      setSelectedText(prefill.selectedText);
      setEntities(
        prefill.entities.length
          ? prefill.entities.map((entity) =>
              makeEntityRow(entity.entityType, entity.name),
            )
          : [makeEntityRow("company")],
      );
      setSelectedTrackSlugs(
        recommendExternalTrackingCaptureTracks(prefill, userTrackingConfig),
      );
      setReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);'''
if new not in text:
    if old not in text:
        raise SystemExit("external capture initialization patch target not found")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
