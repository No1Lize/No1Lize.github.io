import type {
  MarketFinancialSeries,
  MarketMetric,
  MarketPricePoint,
} from "@/lib/market-profile-data";

function linePath(values: Array<number | null>, width: number, height: number, padding = 16) {
  const numeric = values.filter((value): value is number => value !== null);
  if (!numeric.length) return "";
  const min = Math.min(...numeric);
  const max = Math.max(...numeric);
  const span = max - min || 1;
  let started = false;
  return values
    .map((value, index) => {
      if (value === null) return "";
      const x = padding + (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = padding + ((max - value) / span) * (height - padding * 2);
      const command = started ? "L" : "M";
      started = true;
      return `${command}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .filter(Boolean)
    .join(" ");
}

function areaPath(values: number[], width: number, height: number) {
  const path = linePath(values, width, height);
  if (!path) return "";
  return `${path} L${width - 16},${height - 16} L16,${height - 16} Z`;
}

function movingAverage(values: number[], window: number): Array<number | null> {
  return values.map((_, index) => {
    if (index + 1 < window) return null;
    const slice = values.slice(index + 1 - window, index + 1);
    return slice.reduce((sum, value) => sum + value, 0) / window;
  });
}

function formatNumber(value: number, digits = 2) {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: digits,
  }).format(value);
}

function formatVolume(value?: number) {
  if (!value) return "—";
  if (value >= 100_000_000) return `${formatNumber(value / 100_000_000)}亿股`;
  if (value >= 10_000) return `${formatNumber(value / 10_000)}万股`;
  return `${formatNumber(value, 0)}股`;
}

function metricValue(metrics: MarketMetric[], id: string) {
  return metrics.find((metric) => metric.id === id)?.value || "—";
}

export function MarketLineChart({
  points,
  market,
  metrics = [],
}: {
  points: MarketPricePoint[];
  market: "A股" | "港股" | "美股";
  metrics?: MarketMetric[];
}) {
  if (points.length < 2) {
    return (
      <div className="market-chart-empty">
        <strong>等待行情走势同步</strong>
        <p>详情页已创建；定时任务将在可验证数据可用后补充日线走势。</p>
      </div>
    );
  }

  const values = points.map((point) => point.close);
  const latest = points.at(-1)!;
  const previous = points.at(-2)!;
  const change = latest.close - previous.close;
  const changePct = previous.close ? (change / previous.close) * 100 : 0;
  const currency = market === "美股" ? "US$" : market === "港股" ? "HK$" : "¥";
  const intervalHigh = Math.max(...points.map((point) => point.high));
  const intervalLow = Math.min(...points.map((point) => point.low));
  const volumes = points.map((point) => point.volume || 0);
  const maxVolume = Math.max(...volumes, 1);
  const averageVolume = volumes.reduce((sum, value) => sum + value, 0) / volumes.length;
  const ma5 = movingAverage(values, 5);
  const ma20 = movingAverage(values, 20);

  const quoteCards = [
    ["总市值", metricValue(metrics, "marketCap")],
    ["流通市值", metricValue(metrics, "floatMarketCap")],
    ["市盈率", metricValue(metrics, "pe")],
    ["市净率", metricValue(metrics, "pb")],
    ["换手率", metricValue(metrics, "turnover")],
    ["成交额", metricValue(metrics, "amount")],
  ];

  return (
    <div className="market-terminal">
      <div className="market-terminal-toolbar">
        <div>
          <button type="button" data-active="true">日K</button>
          <button type="button">前复权</button>
          <button type="button">近6月</button>
        </div>
        <span>{points.length} 个交易日 · 延迟行情</span>
      </div>

      <div className="market-quote-head">
        <div className="market-last-price" data-direction={change >= 0 ? "up" : "down"}>
          <span>最近收盘</span>
          <strong>{currency}{formatNumber(latest.close)}</strong>
          <small>
            {change >= 0 ? "+" : ""}{formatNumber(change)} · {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
          </small>
        </div>
        <dl className="market-ohlc-grid">
          <div><dt>今开</dt><dd>{formatNumber(latest.open)}</dd></div>
          <div><dt>最高</dt><dd>{formatNumber(latest.high)}</dd></div>
          <div><dt>最低</dt><dd>{formatNumber(latest.low)}</dd></div>
          <div><dt>成交量</dt><dd>{formatVolume(latest.volume)}</dd></div>
          <div><dt>区间高点</dt><dd>{formatNumber(intervalHigh)}</dd></div>
          <div><dt>区间低点</dt><dd>{formatNumber(intervalLow)}</dd></div>
        </dl>
      </div>

      <div className="market-quote-grid">
        {quoteCards.map(([label, value]) => (
          <div key={label}>
            <span>{label}</span>
            <strong>{value}</strong>
          </div>
        ))}
      </div>

      <div className="market-chart-card">
        <div className="market-chart-legend">
          <span><i data-line="close" />收盘价</span>
          <span><i data-line="ma5" />MA5</span>
          <span><i data-line="ma20" />MA20</span>
          <span>区间 {points[0].date} — {latest.date}</span>
        </div>
        <svg
          className="market-chart"
          viewBox="0 0 1000 320"
          role="img"
          aria-label={`${points[0].date}至${latest.date}的收盘价走势`}
        >
          <defs>
            <linearGradient id="market-area" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0" stopColor="var(--green)" stopOpacity="0.26" />
              <stop offset="1" stopColor="var(--green)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[80, 160, 240].map((y) => (
            <line key={y} x1="16" x2="984" y1={y} y2={y} className="market-chart-gridline" />
          ))}
          <path d={areaPath(values, 1000, 320)} fill="url(#market-area)" />
          <path d={linePath(values, 1000, 320)} className="market-price-line" />
          <path d={linePath(ma5, 1000, 320)} className="market-ma5-line" />
          <path d={linePath(ma20, 1000, 320)} className="market-ma20-line" />
        </svg>
        <div className="market-volume-chart" aria-label="成交量柱状图">
          {points.slice(-60).map((point) => (
            <i
              key={point.date}
              title={`${point.date} · ${formatVolume(point.volume)}`}
              style={{ height: `${Math.max(3, ((point.volume || 0) / maxVolume) * 100)}%` }}
            />
          ))}
        </div>
        <div className="market-chart-axis">
          <span>{points[0].date}</span>
          <span>{points[Math.floor(points.length / 2)].date}</span>
          <span>{latest.date}</span>
        </div>
        <div className="market-range-summary">
          <span>区间振幅 <strong>{intervalLow ? (((intervalHigh - intervalLow) / intervalLow) * 100).toFixed(2) : "0.00"}%</strong></span>
          <span>平均成交量 <strong>{formatVolume(averageVolume)}</strong></span>
          <span>最新交易日 <strong>{latest.date}</strong></span>
        </div>
        <p className="market-chart-note">
          数据来自公开延迟行情，仅用于资料展示与历史观察，不构成实时行情或投资建议。
        </p>
      </div>
    </div>
  );
}

export function FinancialSeriesChart({
  series,
}: {
  series: MarketFinancialSeries;
}) {
  if (series.points.length < 2) return null;
  const values = series.points.map((point) => point.value);
  return (
    <div className="financial-series-card">
      <div>
        <span>{series.label}</span>
        <strong>
          {formatNumber(values.at(-1)!)} {series.unit}
        </strong>
      </div>
      <svg viewBox="0 0 600 150" role="img" aria-label={`${series.label}趋势`}>
        <path
          d={linePath(values, 600, 150, 10)}
          fill="none"
          stroke="var(--blue)"
          strokeWidth="2"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="market-chart-axis">
        <span>{series.points[0].period}</span>
        <span>{series.points.at(-1)!.period}</span>
      </div>
    </div>
  );
}
