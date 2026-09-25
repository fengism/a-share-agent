import { getKeyLevelInsight } from "./analysisDecision";

function formatPrice(value: number | null | undefined): string {
  return typeof value === "number" && Number.isFinite(value) && value > 0 ? value.toFixed(2) : "-";
}

function formatDistance(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "-";
  const normalized = Math.abs(value) < 0.05 ? 0 : value;
  return `${normalized >= 0 ? "+" : ""}${normalized.toFixed(1)}%`;
}

export default function AnalysisKeyLevels({
  current,
  support,
  resistance,
  currentLabel = "当前价",
}: {
  current: number | null | undefined;
  currentLabel?: string;
  support: number | null | undefined;
  resistance: number | null | undefined;
}) {
  const insight = getKeyLevelInsight(current, support, resistance);

  return (
    <section className="analysis-key-levels u-card" aria-label="关键点位" data-pdf-capture>
      <div className="analysis-key-levels__header">
        <div className="analysis-key-levels__title">
          <strong>关键点位</strong>
        </div>
        <span className={`analysis-key-levels__status is-${insight.status}`}>
          {insight.label}
        </span>
      </div>
      <div className="analysis-levels">
        <div className="analysis-levels__item is-support">
          <span>支撑位</span>
          <strong>{formatPrice(support)}</strong>
          <small>距支撑 {formatDistance(insight.supportDistancePercent)}</small>
        </div>
        <div className="analysis-levels__item is-current">
          <span>{currentLabel}</span>
          <strong>{formatPrice(current)}</strong>
          <small>区间定位基准</small>
        </div>
        <div className="analysis-levels__item is-resistance">
          <span>压力位</span>
          <strong>{formatPrice(resistance)}</strong>
          <small>距压力 {formatDistance(insight.resistanceDistancePercent)}</small>
        </div>
      </div>
      <p className={`analysis-key-levels__notice is-${insight.status}`} role="status">
        {insight.message}
      </p>
    </section>
  );
}
