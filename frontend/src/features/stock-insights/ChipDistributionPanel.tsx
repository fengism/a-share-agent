import { memo, useMemo } from "react";
import { Card } from "antd";
import ReactEChartsCore from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { useColors, useStyles } from "../../theme/hooks";
import type { ChipCostRange, ChipDistribution } from "../../types/stock";
import "./chip-distribution.css";

function formatPrice(value: number) {
  return value.toFixed(2);
}

function formatRatio(value: number | null) {
  return value == null ? "-" : `${(value * 100).toFixed(2)}%`;
}

function formatRange(value: ChipCostRange) {
  return `${formatPrice(value.low)} – ${formatPrice(value.high)}`;
}

function Metric({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="chip-distribution__metric">
      <span>{label}</span>
      <strong style={tone ? { color: tone } : undefined}>{value}</strong>
    </div>
  );
}

export default memo(function ChipDistributionPanel({
  data,
  embedded = false,
}: {
  data: ChipDistribution;
  embedded?: boolean;
}) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const histogram = useMemo(
    () => [...data.histogram].sort((left, right) => left.price - right.price),
    [data.histogram],
  );
  const chartOption = useMemo(() => ({
    animation: false,
    tooltip: {
      trigger: "axis" as const,
      axisPointer: { type: "shadow" as const },
      valueFormatter: (value: number) => `${(value * 100).toFixed(3)}%`,
    },
    grid: { left: 58, right: 22, top: 12, bottom: 34, containLabel: false },
    xAxis: {
      type: "value" as const,
      min: 0,
      axisLabel: {
        color: colors.textSecondary,
        formatter: (value: number) => `${(value * 100).toFixed(1)}%`,
      },
      splitLine: { lineStyle: { color: colors.border, opacity: 0.45 } },
    },
    yAxis: {
      type: "category" as const,
      data: histogram.map((item) => item.price.toFixed(2)),
      axisLabel: {
        color: colors.textSecondary,
        fontSize: 11,
        interval: Math.max(0, Math.ceil(histogram.length / 6) - 1),
      },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      name: "筹码占比",
      type: "bar" as const,
      barCategoryGap: "5%",
      data: histogram.map((item) => ({
        value: item.ratio,
        itemStyle: {
          color: item.price <= data.price ? colors.up : colors.primary,
          opacity: 0.88,
        },
      })),
    }],
  }), [colors.border, colors.primary, colors.textSecondary, colors.up, data.price, histogram]);

  const content = (
    <div className="chip-distribution-panel-content">
      <div className="chip-distribution__metrics">
        <Metric label="当前价" value={formatPrice(data.price)} tone={colors.textPrimary} />
        <Metric label="筹码峰" value={formatPrice(data.peak_price)} tone={colors.primary} />
        <Metric label="平均成本" value={formatPrice(data.avg_cost)} />
        <Metric label="获利比例" value={formatRatio(data.profit_ratio)} tone={colors.up} />
      </div>
      <div className="chip-distribution__body">
        <div className="chip-distribution__ranges" aria-label="筹码成本区间">
          <div>
            <span>70% 成本区间</span>
            <strong>{formatRange(data.cost_70)}</strong>
            <small>集中度 {formatRatio(data.concentration_70)}</small>
          </div>
          <div>
            <span>90% 成本区间</span>
            <strong>{formatRange(data.cost_90)}</strong>
            <small>集中度 {formatRatio(data.concentration_90)}</small>
          </div>
          <p>红色为现价以下获利筹码，蓝色为现价以上套牢筹码。结果由历史价格与换手率估算，仅供辅助研判。</p>
        </div>
        <div
          className="chip-distribution__chart"
          data-testid="chip-distribution-chart"
          data-pdf-chart="chip-distribution"
          aria-label="筹码价格分布图"
        >
          <ReactEChartsCore echarts={echarts} option={chartOption} notMerge style={{ height: 320 }} />
        </div>
      </div>
    </div>
  );

  if (embedded) {
    return content;
  }

  return (
    <Card
      data-pdf-capture
      data-pdf-group
      size="small"
      className="analysis-chart-card chip-distribution pdf-avoid-break"
      title={<span className="chip-distribution__title">筹码分布（本地估算）</span>}
      extra={<span className="analysis-chart-caption">截至 {data.as_of_date} · 前复权日 K</span>}
      style={{ ...cardStyle, borderTop: `3px solid ${colors.primary}` }}
      styles={{ body: { padding: "14px 16px 16px" } }}
    >
      {content}
    </Card>
  );
});
