import type {
  MarketFinancialSeries,
  MarketPricePoint,
} from "@/lib/market-profile-data";

function linePath(values: number[], width: number, height: number, padding = 16) {
  if (!values.length) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values
    .map((value, index) => {
      const x =
        padding +
        (index / Math.max(values.length - 1, 1)) * (width - padding * 2);
      const y = padding + ((max - value) / span) * (height - padding * 2);
      return `${index ? "L" : "M"}${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function areaPath(values: number[], width: number, height: number) {
  const path = linePath(values, width, height);
  if (!path) return "";
  return `${path} L${width - 16},${height - 16} L16,${height - 16} Z`;
}

function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN", {
    maximumFractionDigits: 2,
  }).format(value);
}

export function MarketLineChart({
  points,
  market,
}: {
  points: MarketPricePoint[];
  market: "A股" | "港股" | "美股";
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

  return (
    <div className="market-chart-card">
      <div className="market-chart-summary">
        <div>
          <span>最近收盘</span>
          <strong>
            {currency}
            {formatNumber(latest.close)}
          </strong>
        </div>
        <div data-direction={change >= 0 ? "up" : "down"}>
          <span>较前一交易日</span>
          <strong>
            {change >= 0 ? "+" : ""}
            {formatNumber(change)} · {changePct >= 0 ? "+" : ""}
            {changePct.toFixed(2)}%
          </strong>
        </div>
        <div>
          <span>区间</span>
          <strong>
            {points[0].date} — {latest.date}
          </strong>
        </div>
      </div>
      <svg
        className="market-chart"
        viewBox="0 0 1000 320"
        role="img"
        aria-label={`${points[0].date}至${latest.date}的收盘价走势`}
      >
        <defs>
          <linearGradient id="market-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="var(--green)" stopOpacity="0.28" />
            <stop offset="1" stopColor="var(--green)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath(values, 1000, 320)} fill="url(#market-area)" />
        <path
          d={linePath(values, 1000, 320)}
          fill="none"
          stroke="var(--green-bright)"
          strokeWidth="3"
          vectorEffect="non-scaling-stroke"
        />
      </svg>
      <div className="market-chart-axis">
        <span>{points[0].date}</span>
        <span>{points[Math.floor(points.length / 2)].date}</span>
        <span>{latest.date}</span>
      </div>
      <p className="market-chart-note">
        日线为延迟公开行情，仅用于资料展示，不构成实时行情或投资建议。
      </p>
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
