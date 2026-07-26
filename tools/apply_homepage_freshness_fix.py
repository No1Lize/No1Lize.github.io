#!/usr/bin/env python3
"""Apply the homepage freshness and visible time-sorting repair once."""

from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "components" / "dashboard.tsx"

REPLACEMENTS = [
    (
        '  const [query, setQuery] = useState("");\n  const [showMethod, setShowMethod] = useState(false);',
        '  const [query, setQuery] = useState("");\n  const [sortOrder, setSortOrder] = useState<"newest" | "oldest">("newest");\n  const [showMethod, setShowMethod] = useState(false);',
    ),
    (
        '''  const normalizedQuery = query.trim().toLowerCase();\n  const visibleEvents = useMemo(''',
        '''  const latestPublishedAt = useMemo(\n    () =>\n      activeArticles.reduce(\n        (latest, item) => (item.publishedAt > latest ? item.publishedAt : latest),\n        "",\n      ),\n    [activeArticles],\n  );\n  const processedAt = formatTaipeiDate(generatedAt);\n  const freshnessLabel = !isLive\n    ? "内置快照"\n    : latestPublishedAt === processedAt\n      ? "当日情报已更新"\n      : "内容待刷新";\n  const normalizedQuery = query.trim().toLowerCase();\n  const visibleEvents = useMemo(''',
    ),
    (
        '''        .sort(\n          (a, b) =>\n            b.publishedAt.localeCompare(a.publishedAt) ||\n            b.importance - a.importance,\n        ),\n    [activeArticles, eventType, normalizedQuery, region],''',
        '''        .sort((a, b) => {\n          const timeComparison =\n            sortOrder === "newest"\n              ? b.publishedAt.localeCompare(a.publishedAt)\n              : a.publishedAt.localeCompare(b.publishedAt);\n          return timeComparison || b.importance - a.importance;\n        }),\n    [activeArticles, eventType, normalizedQuery, region, sortOrder],''',
    ),
    (
        '''            <span>公开资料快照 · {generatedAt.slice(0, 10)}</span>\n            <span className="status-pill"><i /> {isLive ? "已同步" : "内置快照"}</span>''',
        '''            <span>最新情报 · {latestPublishedAt || "暂无"}</span>\n            <span className="status-pill"><i /> {freshnessLabel}</span>''',
    ),
    (
        '''          <p>{qualityGate?.passed === false ? "数据质量门未通过" : "当前启用赛道的可追溯公开情报"}</p>''',
        '''          <p>\n            {qualityGate?.passed === false\n              ? "数据质量门未通过"\n              : isLive && latestPublishedAt !== processedAt\n                ? "数据已处理，但最新情报仍待刷新"\n                : "当前启用赛道的可追溯公开情报"}\n          </p>''',
    ),
    (
        '''            <span>{platformCount} 类平台 · {sectorCount} 个启用赛道</span>''',
        '''            <span>{platformCount} 类平台 · {sectorCount} 个启用赛道</span>\n            <span>数据处理 · {processedAt}</span>''',
    ),
    (
        '''            <select value={eventType} onChange={(event) => setEventType(event.target.value as (typeof eventTypes)[number])} aria-label="事件类型">\n              {eventTypes.map((item) => <option key={item}>{item}</option>)}\n            </select>\n            <label className="inline-search">''',
        '''            <select value={eventType} onChange={(event) => setEventType(event.target.value as (typeof eventTypes)[number])} aria-label="事件类型">\n              {eventTypes.map((item) => <option key={item}>{item}</option>)}\n            </select>\n            <select\n              value={sortOrder}\n              onChange={(event) => setSortOrder(event.target.value as "newest" | "oldest")}\n              aria-label="时间排序"\n            >\n              <option value="newest">时间：最新优先</option>\n              <option value="oldest">时间：最早优先</option>\n            </select>\n            <label className="inline-search">''',
    ),
    (
        '''function EventTitle({ item }: { item: IntelligenceEvent }) {''',
        '''function formatTaipeiDate(value: string) {\n  const timestamp = new Date(value);\n  if (Number.isNaN(timestamp.getTime())) return value.slice(0, 10);\n  const parts = new Intl.DateTimeFormat("en-CA", {\n    timeZone: "Asia/Taipei",\n    year: "numeric",\n    month: "2-digit",\n    day: "2-digit",\n  }).formatToParts(timestamp);\n  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]));\n  return `${values.year}-${values.month}-${values.day}`;\n}\n\nfunction EventTitle({ item }: { item: IntelligenceEvent }) {''',
    ),
]


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    for old, new in REPLACEMENTS:
        if new in text:
            continue
        if old not in text:
            raise SystemExit(f"Expected dashboard block not found:\n{old}")
        text = text.replace(old, new, 1)
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
