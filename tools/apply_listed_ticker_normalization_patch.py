#!/usr/bin/env python3
"""Apply or repair the listed-company ticker normalization patch safely."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPORT_LINE = 'import { normalizeMarketTicker } from "@/lib/listed-company-identity";\n'


def ensure_replacement(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one guarded match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def normalize_import(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(IMPORT_LINE, "")
    anchor = 'import { ipoCompanies } from "@/lib/catalog-data";\n'
    if text.count(anchor) != 1:
        raise RuntimeError(f"{path}: catalog import anchor changed")
    path.write_text(text.replace(anchor, anchor + IMPORT_LINE, 1), encoding="utf-8")


def patch_user_tracking() -> None:
    path = ROOT / "lib" / "user-tracking.ts"
    normalize_import(path)
    ensure_replacement(
        path,
        '''  const name = cleanText(raw.name, 80);\n  const ticker = cleanText(raw.ticker, 30).toUpperCase().replace(/\\s+/g, "");\n  const market = MARKETS.includes(raw.market as TrackingMarket)\n    ? (raw.market as TrackingMarket)\n    : null;\n  if (!name || !ticker || !market) return null;\n''',
        '''  const name = cleanText(raw.name, 80);\n  const market = MARKETS.includes(raw.market as TrackingMarket)\n    ? (raw.market as TrackingMarket)\n    : null;\n  if (!name || !market) return null;\n  const ticker = normalizeMarketTicker(market, cleanText(raw.ticker, 30));\n  if (!ticker) return null;\n''',
    )
    ensure_replacement(
        path,
        '''    ticker: company.ticker,\n    market: company.market,\n''',
        '''    ticker:\n      normalizeMarketTicker(company.market, company.ticker) || company.ticker,\n    market: company.market,\n''',
    )


def patch_panel() -> None:
    path = ROOT / "components" / "user-tracking-panel.tsx"
    normalize_import(path)
    ensure_replacement(
        path,
        '''        (item.market === company.market && item.ticker === company.ticker),\n''',
        '''        (item.market === company.market &&\n          normalizeMarketTicker(item.market, item.ticker) === company.ticker),\n''',
    )
    ensure_replacement(
        path,
        '''      ticker: catalog.ticker.toUpperCase(),\n''',
        '''      ticker:\n        normalizeMarketTicker(catalog.market, catalog.ticker) ||\n        catalog.ticker.toUpperCase(),\n''',
    )
    ensure_replacement(
        path,
        '''    const ticker = listedDraft.ticker\n      .trim()\n      .toUpperCase()\n      .replace(/\\s+/g, "");\n    if (!name || !ticker) {\n      setMessage("请填写上市公司名称和股票代码。", "error");\n      return;\n    }\n''',
        '''    const ticker = normalizeMarketTicker(\n      listedDraft.market,\n      listedDraft.ticker,\n    );\n    if (!name) {\n      setMessage("请填写上市公司名称。", "error");\n      return;\n    }\n    if (!ticker) {\n      setMessage(\n        listedDraft.market === "A股"\n          ? "A股代码应为 6 位数字，可输入 600519、600519.SH 或 SH600519。"\n          : listedDraft.market === "港股"\n            ? "港股代码可输入 700、0700、00700、0700.HK 或 HK0700。"\n            : "美股代码格式无效，例如 AAPL、BRK.B。",\n        "error",\n      );\n      return;\n    }\n''',
    )
    ensure_replacement(
        path,
        '''        company.market === listedDraft.market &&\n        company.ticker.toUpperCase() === ticker,\n''',
        '''        company.market === listedDraft.market &&\n        normalizeMarketTicker(company.market, company.ticker) === ticker,\n''',
    )


def main() -> int:
    patch_user_tracking()
    patch_panel()
    print("Listed-company ticker normalization is present and imports are clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
