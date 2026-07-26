#!/usr/bin/env python3
"""Merge the spaced IDG catalog label into the Qingke-ranked institution entry."""

from pathlib import Path

path = Path(__file__).resolve().parents[1] / "lib" / "institution-ranking-data.ts"
text = path.read_text(encoding="utf-8")
old = '''  const matchedName =
    institution.name === "深创投" ? "深创投集团" :
    institution.name === "高瓴" ? "高瓴投资" :
    institution.name;
'''
new = '''  const matchedName =
    institution.name === "IDG 资本" ? "IDG资本" :
    institution.name === "深创投" ? "深创投集团" :
    institution.name === "高瓴" ? "高瓴投资" :
    institution.name;
'''
if new in text:
    print("IDG alias normalization already applied.")
elif text.count(old) != 1:
    raise SystemExit(f"Expected one institution alias block, found {text.count(old)}")
else:
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print("Applied IDG alias normalization.")
