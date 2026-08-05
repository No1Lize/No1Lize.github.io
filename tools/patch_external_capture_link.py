#!/usr/bin/env python3
"""One-time patch adding the external capture entry to the tracking inbox."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "components" / "tracking-capture-inbox.tsx"
text = path.read_text(encoding="utf-8")
text = text.replace(
    'import { BookOpen, ExternalLink, Inbox, RefreshCw } from "lucide-react";',
    'import { BookOpen, ExternalLink, Globe2, Inbox, RefreshCw } from "lucide-react";',
    1,
)
old = '''        <div className={styles.headerActions}>
          <Link href="/tracking/entities" className={styles.libraryLink}>'''
new = '''        <div className={styles.headerActions}>
          <Link href="/tracking/capture" className={styles.libraryLink}>
            <Globe2 size={15} />外部网页采集
          </Link>
          <Link href="/tracking/entities" className={styles.libraryLink}>'''
if new not in text:
    if old not in text:
        raise SystemExit("tracking capture inbox header patch target not found")
    text = text.replace(old, new, 1)
path.write_text(text, encoding="utf-8")
