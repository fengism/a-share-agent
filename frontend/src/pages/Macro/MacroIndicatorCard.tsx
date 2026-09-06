import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Card, Col, Empty, Row, Statistic, Tag, Tooltip, Typography } from "antd";
import { useColors } from "../../theme/hooks";
import { APP_FONT_FAMILY, APP_FONT_SIZE } from "../../theme/typography";
import type { MacroIndicator } from "../../types/stock";

const { Text } = Typography;

function scaleMetricValue(value: number, divisor = 1) {
  if (divisor === 1) return value;
  return Number((value / divisor).toFixed(12));
}

interface FieldDef {
  key: string;
  label: string;
  color?: string;
  unit?: string;
  precision?: number;
  valueDivisor?: number;
}

interface MacroIndicatorCardProps {
  title: string;
  latest: Record<string, string | number | null> | null;
  trend: Record<string, string | number | null>[];
  fields: FieldDef[];
  dateKey?: string;
  chartType?: "line" | "bar";
  metadata?: MacroIndicator;
}

export default function MacroIndicatorCard({
  title,
  latest,
  trend,
  fields,
  dateKey = "TIME",
  chartType = "line",
  metadata,
}: MacroIndicatorCardProps) {
  const c = useColors();

  function valueColor(value: number | null | undefined) {
    if (value == null) return c.textSecondary;
    if (value > 0) return c.up;
    if (value < 0) return c.down;
    return c.textSecondary;
  }

  const chartOption = useMemo(() => {
    if (!trend || trend.length === 0) return null;

    const dates = trend
      .map((item) => item[dateKey])
      .filter(Boolean)
      .reverse();

    const chartFields = fields.filter((f) => trend.some((item) => item[f.key] != null));
    const hasRateSeries = chartFields.some((field) => field.unit === "%");
    const hasLevelSeries = chartFields.some((field) => field.unit !== "%");
    const useDualAxis = hasRateSeries && hasLevelSeries;
    const levelUnits = Array.from(new Set(
      chartFields
        .filter((field) => field.unit !== "%")
        .map((field) => field.unit)
        .filter((unit): unit is string => Boolean(unit)),
    ));
    const levelAxisName = levelUnits.length === 1 ? levelUnits[0] : levelUnits.length > 1 ? "规模" : undefined;

    const series = chartFields.map((f) => ({
      name: f.label,
      type: chartType,
      smooth: chartType === "line",
      showSymbol: false,
      symbol: "circle",
      symbolSize: 6,
      yAxisIndex: useDualAxis && f.unit === "%" ? 1 : 0,
      data: trend
        .map((item) => {
          const value = item[f.key];
          return typeof value === "number" ? scaleMetricValue(value, f.valueDivisor) : value;
        })
        .filter((_, i) => trend[i][dateKey] != null)
        .reverse(),
      lineStyle: { width: 2, color: f.color || c.primary },
      itemStyle: { color: f.color || c.primary },
      emphasis: { focus: "series" },
    }));

    const valueAxis = {
      type: "value",
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: { color: c.textMuted, fontFamily: APP_FONT_FAMILY, fontSize: APP_FONT_SIZE.xs, margin: 10 },
      splitLine: { lineStyle: { color: c.border, type: "dashed" } },
    };
    const denseLegend = series.length > 4;

    return {
      textStyle: { fontFamily: APP_FONT_FAMILY },
      animationDuration: 400,
      tooltip: {
        trigger: "axis",
        backgroundColor: c.elevatedBg,
        borderColor: c.border,
        textStyle: { color: c.textPrimary, fontFamily: APP_FONT_FAMILY, fontSize: APP_FONT_SIZE.sm },
      },
      legend: {
        type: denseLegend ? "scroll" : "plain",
        data: series.map((item) => item.name),
        textStyle: { color: c.textSecondary, fontFamily: APP_FONT_FAMILY, fontSize: APP_FONT_SIZE.sm },
        itemWidth: 16,
        itemHeight: 8,
        top: 2,
      },
      grid: { left: 8, right: useDualAxis ? 34 : 12, top: denseLegend ? 46 : 38, bottom: 8, containLabel: true },
      xAxis: {
        type: "category",
        data: dates,
        boundaryGap: chartType === "bar",
        axisLine: { lineStyle: { color: c.border } },
        axisTick: { show: false },
        axisLabel: { color: c.textMuted, fontFamily: APP_FONT_FAMILY, fontSize: APP_FONT_SIZE.xs, rotate: 30, margin: 12 },
      },
      yAxis: useDualAxis
        ? [
            { ...valueAxis, name: levelAxisName },
            {
              ...valueAxis,
              name: "%",
              position: "right",
              splitLine: { show: false },
            },
          ]
        : { ...valueAxis, name: hasRateSeries ? "%" : levelAxisName },
      series,
    };
  }, [trend, fields, dateKey, chartType, c]);

  if (!latest || fields.length === 0) {
    return (
      <Card className="macro-indicator-card macro-indicator-card--empty">
        <div className="macro-indicator-card__empty-title">{title}</div>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可用数据" />
      </Card>
    );
  }

  const dateValue = metadata?.latest_period ?? latest[dateKey];
  const metricColumnSpan = Math.max(6, Math.floor(24 / Math.min(fields.length, 4)));
  const sourceLabel = metadata?.source === "nbs"
    ? "国家统计局"
    : metadata?.source === "eastmoney" ? "东方财富" : metadata?.source;

  return (
    <Card
      className="macro-indicator-card u-card-interactive"
      title={
        <div className="macro-indicator-card__header">
          <span className="macro-indicator-card__title">{title}</span>
          <div className="macro-indicator-card__meta">
            {sourceLabel ? (
              <Tooltip title={metadata?.source_api || undefined}>
                <Tag className="macro-indicator-card__tag" color={metadata?.source === "nbs" ? "blue" : undefined}>{sourceLabel}</Tag>
              </Tooltip>
            ) : null}
            {metadata?.is_fallback ? <Tag className="macro-indicator-card__tag" color="warning">fallback</Tag> : null}
            {metadata?.is_stale ? <Tag className="macro-indicator-card__tag" color="error">数据滞后</Tag> : null}
            {!metadata?.is_stale && metadata?.stale_fields?.length ? <Tag className="macro-indicator-card__tag" color="warning">部分字段滞后</Tag> : null}
            {dateValue ? (
              <Text className="macro-indicator-card__date">
                <span>数据期</span>{String(dateValue)}
              </Text>
            ) : null}
          </div>
        </div>
      }
    >
      <Row className="macro-indicator-card__metrics" gutter={[10, 10]}>
        {fields.map((f) => {
          const val = latest[f.key];
          const rawNumVal = typeof val === "number" ? val : null;
          const scaledNumVal = rawNumVal == null ? null : scaleMetricValue(rawNumVal, f.valueDivisor);
          const precision = f.precision ?? (scaledNumVal != null && Math.abs(scaledNumVal) < 10 ? 2 : 1);
          const numVal = scaledNumVal == null ? null : Number(scaledNumVal.toFixed(precision));
          return (
            <Col xs={12} sm={8} lg={metricColumnSpan} key={f.key}>
              <div
                className={`macro-indicator-card__metric macro-indicator-card__metric--${f.unit === "%" ? "rate" : "level"}`}
              >
                <Text className="macro-indicator-card__metric-label">
                  <Tooltip title={metadata?.field_periods?.[f.key] ? `数据周期：${metadata.field_periods[f.key]}` : undefined}>
                    <span>{f.label}</span>
                  </Tooltip>
                  {metadata?.stale_fields?.includes(f.key) ? <Tag color="warning" className="macro-indicator-card__stale-tag">滞后</Tag> : null}
                </Text>
                <Statistic
                  value={numVal ?? undefined}
                  precision={numVal != null ? precision : undefined}
                  suffix={f.unit}
                  styles={{
                    content: {
                      fontFamily: "var(--c-font-mono)",
                      fontWeight: 700,
                      color: f.color || valueColor(numVal),
                    },
                  }}
                />
              </div>
            </Col>
          );
        })}
      </Row>
      {chartOption ? (
        <section className="macro-indicator-card__chart" aria-label={`${title}历史趋势`}>
          <div className="macro-indicator-card__chart-heading">历史趋势</div>
          <ReactECharts echarts={echarts} option={chartOption} className="macro-indicator-card__echart" />
        </section>
      ) : null}
    </Card>
  );
}
