import type { MonthlyPoint, TrendMetric } from "./presentation";
import { displayMonth, seriesValue } from "./presentation";

const SERIES_COLORS = ["#003675", "#087f78", "#a44800", "#0b5ea8", "#a51d2d", "#5b21b6", "#0f766e", "#b45309", "#1d4ed8", "#9f1239"];

interface ChartSeries {
  key: string;
  label: string;
  points: MonthlyPoint[];
}

interface Props {
  series: ChartSeries[];
  metric: TrendMetric;
}

export function seriesColor(index: number): string {
  return SERIES_COLORS[index % SERIES_COLORS.length]!;
}

export default function TrendChart({ series, metric }: Props) {
  const months = [...new Set(series.flatMap((item) => item.points.map((point) => point.month)))].sort();
  const values = series.flatMap((item) => item.points.map((point) => seriesValue(point, metric))).filter((value): value is number => value != null);
  const width = 720;
  const height = 260;
  const pad = { top: 16, right: 16, bottom: 36, left: 64 };
  const innerWidth = width - pad.left - pad.right;
  const innerHeight = height - pad.top - pad.bottom;
  const maxValue = Math.max(0, ...values);
  const yMax = maxValue === 0 ? 1 : maxValue;
  const x = (index: number) => pad.left + (months.length <= 1 ? innerWidth / 2 : (index / (months.length - 1)) * innerWidth);
  const y = (value: number) => pad.top + innerHeight - (value / yMax) * innerHeight;
  const ticks = [0, yMax / 2, yMax];
  const metricLabel = metric === "tx_count" ? "거래 건수" : "공급금액";
  const monthStep = Math.max(1, Math.ceil(months.length / 6));

  if (!months.length || !values.length) {
    return <p className="empty-copy">선택한 기간에 그릴 월별 값이 없습니다.</p>;
  }

  return (
    <figure className="trend-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`선택 품목의 월별 ${metricLabel} 추세`}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="trend-chart__grid" x1={pad.left} x2={width - pad.right} y1={y(tick)} y2={y(tick)} />
            <text className="trend-chart__tick" x={pad.left - 8} y={y(tick) + 4} textAnchor="end">
              {formatTick(tick, metric)}
            </text>
          </g>
        ))}
        {months.map((month, index) => (
          index === 0 || index === months.length - 1 || index % monthStep === 0 ? (
            <text key={month} className="trend-chart__tick" x={x(index)} y={height - 10} textAnchor="middle">
              {displayMonth(month)}
            </text>
          ) : null
        ))}
        {series.map((item, seriesIndex) => (
          <g key={item.key}>
            <path d={linePath(item.points, months, metric, x, y)} fill="none" stroke={seriesColor(seriesIndex)} strokeWidth="2.5" />
            {months.map((month, index) => {
              const value = valueAt(item.points, month, metric);
              return value == null ? null : (
                <circle key={`${item.key}:${month}`} cx={x(index)} cy={y(value)} r="3.5" fill={seriesColor(seriesIndex)}>
                  <title>{`${item.label} · ${displayMonth(month)} · ${formatTick(value, metric)}`}</title>
                </circle>
              );
            })}
          </g>
        ))}
      </svg>
      <figcaption>
        <ul className="trend-legend">
          {series.map((item, index) => (
            <li key={item.key}>
              <span className="trend-legend__swatch" style={{ background: seriesColor(index) }} />
              {item.label}
            </li>
          ))}
        </ul>
      </figcaption>
      <table className="visually-hidden">
        <caption>{`월별 ${metricLabel}`}</caption>
        <thead>
          <tr>
            <th>품목</th>
            {months.map((month) => <th key={month}>{displayMonth(month)}</th>)}
          </tr>
        </thead>
        <tbody>
          {series.map((item) => (
            <tr key={item.key}>
              <th scope="row">{item.label}</th>
              {months.map((month) => {
                const value = valueAt(item.points, month, metric);
                return <td key={month}>{value == null ? "없음" : formatTick(value, metric)}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

function valueAt(points: MonthlyPoint[], month: string, metric: TrendMetric): number | null {
  const point = points.find((entry) => entry.month === month);
  return point ? seriesValue(point, metric) : null;
}

function linePath(
  points: MonthlyPoint[],
  months: string[],
  metric: TrendMetric,
  x: (index: number) => number,
  y: (value: number) => number,
): string {
  let drawing = false;
  return months.reduce((path, month, index) => {
    const value = valueAt(points, month, metric);
    if (value == null) {
      drawing = false;
      return path;
    }
    const command = `${drawing ? "L" : "M"} ${x(index)} ${y(value)}`;
    drawing = true;
    return path ? `${path} ${command}` : command;
  }, "");
}

function formatTick(value: number, metric: TrendMetric): string {
  if (metric === "amount_sum_clean" && value >= 100_000_000) {
    return `${(value / 100_000_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}억`;
  }
  if (value >= 10_000) return `${(value / 10_000).toLocaleString("ko-KR", { maximumFractionDigits: 1 })}만`;
  return value.toLocaleString("ko-KR", { maximumFractionDigits: metric === "tx_count" ? 0 : 1 });
}
