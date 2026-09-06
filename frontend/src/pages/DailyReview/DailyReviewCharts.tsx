import type { ReactNode } from "react";
import type { DailyReviewDataSnapshot } from "../../types/dailyReview";

interface DailyReviewChartsProps {
  snapshot: DailyReviewDataSnapshot;
}

interface NamedValue {
  name: string;
  value: number;
}

const UP_COLOR = "#ef4444";
const DOWN_COLOR = "#16a34a";
const NEUTRAL_COLOR = "#94a3b8";
const PRIMARY_COLOR = "#2563eb";
const GRID_COLOR = "var(--c-border, #e2e8f0)";
const TEXT_COLOR = "var(--c-text-secondary, #475569)";
const PRIMARY_TEXT_COLOR = "var(--c-text-primary, #0f172a)";

function finiteNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function namedValues(items: Record<string, unknown>[] | undefined, limit: number): NamedValue[] {
  return (items ?? []).flatMap((item) => {
    const name = String(item.name ?? item.code ?? "").trim();
    const value = finiteNumber(item.change_pct);
    return name && value !== null ? [{ name, value }] : [];
  }).slice(0, limit);
}

function formatPercent(value: number): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatAmount(value: number): string {
  const absolute = Math.abs(value);
  if (absolute >= 1e8) return `${(value / 1e8).toFixed(1)} 亿元`;
  if (absolute >= 1e4) return `${(value / 1e4).toFixed(1)} 万元`;
  return `${value.toFixed(0)} 元`;
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <section className="daily-review-chart-card">
      <div className="daily-review-chart-card__header">
        <strong>{title}</strong>
        <span>{subtitle}</span>
      </div>
      {children}
    </section>
  );
}

function BreadthChart({ snapshot }: DailyReviewChartsProps) {
  const raw = snapshot.market_statistics ?? {};
  const definitions = [
    ["上涨", "up_count", UP_COLOR],
    ["下跌", "down_count", DOWN_COLOR],
    ["平盘", "flat_count", NEUTRAL_COLOR],
    ["涨停", "limit_up_count", "#dc2626"],
    ["跌停", "limit_down_count", "#15803d"],
  ] as const;
  const values = definitions.flatMap(([name, key, color]) => {
    const value = finiteNumber(raw[key]);
    return value === null ? [] : [{ name, value: Math.max(value, 0), color }];
  });
  if (!values.length) return null;
  const max = Math.max(...values.map((item) => item.value), 1);
  const rowHeight = 34;
  const height = 26 + values.length * rowHeight;

  return (
    <ChartCard title="市场涨跌分布" subtitle="上涨 / 下跌家数与涨跌停情绪">
      <svg data-testid="daily-review-breadth-chart" role="img" aria-label="市场涨跌分布图" viewBox={`0 0 560 ${height}`}>
        {values.map((item, index) => {
          const y = 18 + index * rowHeight;
          const width = Math.max((item.value / max) * 350, item.value > 0 ? 3 : 0);
          return (
            <g key={item.name}>
              <text x="0" y={y + 14} fill={TEXT_COLOR} fontSize="13">{item.name}</text>
              <rect x="58" y={y} width="350" height="20" rx="5" fill="var(--c-nested-bg, #f1f5f9)" />
              <rect x="58" y={y} width={width} height="20" rx="5" fill={item.color} opacity="0.9" />
              <text x="422" y={y + 14} fill={PRIMARY_TEXT_COLOR} fontSize="13" fontWeight="700">{item.value.toLocaleString("zh-CN")} 家</text>
            </g>
          );
        })}
      </svg>
    </ChartCard>
  );
}

function IndexChart({ snapshot }: DailyReviewChartsProps) {
  const values = namedValues(snapshot.indices, 6);
  if (!values.length) return null;
  const max = Math.max(...values.map((item) => Math.abs(item.value)), 1);
  const center = 320;
  const maxWidth = 176;
  const rowHeight = 34;
  const height = 24 + values.length * rowHeight;

  return (
    <ChartCard title="核心指数表现" subtitle="主要指数当日涨跌幅">
      <svg data-testid="daily-review-index-chart" role="img" aria-label="核心指数涨跌幅图" viewBox={`0 0 560 ${height}`}>
        <line x1={center} x2={center} y1="4" y2={height - 4} stroke={GRID_COLOR} strokeWidth="1" />
        {values.map((item, index) => {
          const y = 14 + index * rowHeight;
          const width = Math.max((Math.abs(item.value) / max) * maxWidth, item.value === 0 ? 0 : 3);
          const x = item.value >= 0 ? center : center - width;
          return (
            <g key={`${item.name}-${index}`}>
              <text x="0" y={y + 14} fill={TEXT_COLOR} fontSize="13">{item.name}</text>
              <rect x={x} y={y} width={width} height="20" rx="4" fill={item.value >= 0 ? UP_COLOR : DOWN_COLOR} opacity="0.9" />
              <text x="548" y={y + 14} textAnchor="end" fill={item.value >= 0 ? UP_COLOR : DOWN_COLOR} fontSize="13" fontWeight="700">{formatPercent(item.value)}</text>
            </g>
          );
        })}
      </svg>
    </ChartCard>
  );
}

function SectorChart({ snapshot }: DailyReviewChartsProps) {
  const strong = namedValues(snapshot.top_sectors, 5).map((item) => ({ ...item, kind: "strong" as const }));
  const weak = namedValues(snapshot.bottom_sectors, 5).map((item) => ({ ...item, kind: "weak" as const }));
  const values = [...strong, ...weak];
  if (!values.length) return null;
  const max = Math.max(...values.map((item) => Math.abs(item.value)), 1);
  const center = 310;
  const maxWidth = 184;
  const rowHeight = 31;
  const height = 32 + values.length * rowHeight;

  return (
    <ChartCard title="板块强弱对比" subtitle="领涨与领跌板块双向对照">
      <svg data-testid="daily-review-sector-chart" role="img" aria-label="板块强弱对比图" viewBox={`0 0 560 ${height}`}>
        <line x1={center} x2={center} y1="4" y2={height - 4} stroke={GRID_COLOR} strokeWidth="1" />
        {values.map((item, index) => {
          const y = 18 + index * rowHeight;
          const positive = item.kind === "strong";
          const width = Math.max((Math.abs(item.value) / max) * maxWidth, item.value === 0 ? 0 : 3);
          return (
            <g key={`${item.kind}-${item.name}-${index}`}>
              <text x="0" y={y + 13} fill={TEXT_COLOR} fontSize="12">{item.name}</text>
              <rect x={positive ? center : center - width} y={y} width={width} height="18" rx="4" fill={positive ? UP_COLOR : DOWN_COLOR} opacity="0.9" />
              <text x="548" y={y + 13} textAnchor="end" fill={positive ? UP_COLOR : DOWN_COLOR} fontSize="12" fontWeight="700">{formatPercent(item.value)}</text>
            </g>
          );
        })}
      </svg>
    </ChartCard>
  );
}

function VolumeChart({ snapshot }: DailyReviewChartsProps) {
  const raw = snapshot.market_volume ?? {};
  const definitions = [
    ["当日成交额", "amount", PRIMARY_COLOR],
    ["前一日成交额", "amount_before_one_day", "#7c3aed"],
    ["60 日均值", "amount_average_60_day", "#0891b2"],
  ] as const;
  const values = definitions.flatMap(([name, key, color]) => {
    const value = finiteNumber(raw[key]);
    return value === null ? [] : [{ name, value: Math.max(value, 0), color }];
  });
  if (!values.length) return null;
  const max = Math.max(...values.map((item) => item.value), 1);

  return (
    <ChartCard title="市场成交额" subtitle="当日、前一日与 60 日均值">
      <svg data-testid="daily-review-volume-chart" role="img" aria-label="市场成交额对比图" viewBox="0 0 560 158">
        <line x1="48" x2="536" y1="124" y2="124" stroke={GRID_COLOR} strokeWidth="1" />
        {values.map((item, index) => {
          const width = 92;
          const x = 74 + index * 158;
          const barHeight = (item.value / max) * 82;
          return (
            <g key={item.name}>
              <text x={x + width / 2} y={116 - barHeight} textAnchor="middle" fill={PRIMARY_TEXT_COLOR} fontSize="11" fontWeight="700">{formatAmount(item.value)}</text>
              <rect x={x} y={122 - barHeight} width={width} height={barHeight} rx="6" fill={item.color} opacity="0.9" />
              <text x={x + width / 2} y="146" textAnchor="middle" fill={TEXT_COLOR} fontSize="12">{item.name}</text>
            </g>
          );
        })}
      </svg>
    </ChartCard>
  );
}

export default function DailyReviewCharts({ snapshot }: DailyReviewChartsProps) {
  const statistics = snapshot.market_statistics ?? {};
  const volume = snapshot.market_volume ?? {};
  const hasBreadth = ["up_count", "down_count", "flat_count", "limit_up_count", "limit_down_count"]
    .some((key) => finiteNumber(statistics[key]) !== null);
  const hasIndices = namedValues(snapshot.indices, 6).length > 0;
  const hasSectors = namedValues(snapshot.top_sectors, 5).length > 0
    || namedValues(snapshot.bottom_sectors, 5).length > 0;
  const hasVolume = ["amount", "amount_before_one_day", "amount_average_60_day"]
    .some((key) => finiteNumber(volume[key]) !== null);

  if (!hasBreadth && !hasIndices && !hasSectors && !hasVolume) {
    return <div className="daily-review-charts-empty">暂无可视化数据</div>;
  }

  return (
    <div className="daily-review-charts-grid">
      {hasBreadth ? <BreadthChart snapshot={snapshot} /> : null}
      {hasIndices ? <IndexChart snapshot={snapshot} /> : null}
      {hasSectors ? <SectorChart snapshot={snapshot} /> : null}
      {hasVolume ? <VolumeChart snapshot={snapshot} /> : null}
    </div>
  );
}
