import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Card, Col, Empty, Row, Space, Statistic, Tag, Tooltip, Typography } from "antd";
import { useColors, useStyles } from "../../theme/hooks";
import type { MacroIndicator } from "../../types/stock";

const { Text } = Typography;

interface FieldDef {
  key: string;
  label: string;
  color?: string;
  unit?: string;
  precision?: number;
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
  const { cardStyle } = useStyles();

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

    const series = fields
      .filter((f) => trend.some((item) => item[f.key] != null))
      .map((f) => ({
        name: f.label,
        type: chartType,
        smooth: chartType === "line",
        showSymbol: false,
        data: trend
          .map((item) => item[f.key])
          .filter((_, i) => trend[i][dateKey] != null)
          .reverse(),
        lineStyle: { width: 2, color: f.color || c.primary },
        itemStyle: { color: f.color || c.primary },
      }));

    return {
      tooltip: { trigger: "axis" },
      legend: {
        data: fields.map((f) => f.label),
        textStyle: { color: c.textSecondary, fontSize: 11 },
        top: 4,
      },
      grid: { left: 48, right: 16, top: 36, bottom: 28 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: c.textMuted, fontSize: 10, rotate: 30 },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: c.textMuted, fontSize: 10 },
        splitLine: { lineStyle: { color: `${c.textSecondary}1f` } },
      },
      series,
    };
  }, [trend, fields, dateKey, chartType, c]);

  if (!latest || fields.length === 0) {
    return (
      <Card style={{ ...cardStyle, minHeight: 200 }}>
        <Text style={{ color: c.textSecondary }}>{title} 暂无数据</Text>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无可用数据" />
      </Card>
    );
  }

  const dateValue = metadata?.latest_period ?? latest[dateKey];
  const sourceLabel = metadata?.source === "nbs"
    ? "国家统计局"
    : metadata?.source === "eastmoney" ? "东方财富" : metadata?.source;

  return (
    <Card
      style={cardStyle}
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <span style={{ color: c.textPrimary, fontWeight: 600 }}>{title}</span>
          <Space size={4} wrap>
            {sourceLabel ? (
              <Tooltip title={metadata?.source_api || undefined}>
                <Tag color={metadata?.source === "nbs" ? "blue" : undefined}>{sourceLabel}</Tag>
              </Tooltip>
            ) : null}
            {metadata?.is_fallback ? <Tag color="warning">fallback</Tag> : null}
            {metadata?.is_stale ? <Tag color="error">数据滞后</Tag> : null}
            {!metadata?.is_stale && metadata?.stale_fields?.length ? <Tag color="warning">部分字段滞后</Tag> : null}
            {dateValue && (
              <Text style={{ color: c.textMuted, fontSize: 12 }}>{String(dateValue)}</Text>
            )}
          </Space>
        </div>
      }
      styles={{ body: { padding: "12px 16px" } }}
    >
      <Row gutter={[12, 8]}>
        {fields.map((f) => {
          const val = latest[f.key];
          const numVal = typeof val === "number" ? val : null;
          const precision = f.precision ?? (numVal != null && Math.abs(numVal) < 10 ? 2 : 1);
          return (
            <Col xs={12} sm={8} md={6} key={f.key}>
              <div style={{ textAlign: "center" }}>
                <Text style={{ color: c.textMuted, fontSize: 11, display: "block", marginBottom: 2 }}>
                  <Tooltip title={metadata?.field_periods?.[f.key] ? `数据周期：${metadata.field_periods[f.key]}` : undefined}>
                    <span>{f.label}</span>
                  </Tooltip>
                  {metadata?.stale_fields?.includes(f.key) ? <Tag color="warning" style={{ marginInlineStart: 4, marginInlineEnd: 0 }}>滞后</Tag> : null}
                </Text>
                <Statistic
                  value={numVal ?? undefined}
                  precision={numVal != null ? precision : undefined}
                  suffix={f.unit}
                  styles={{
                    content: {
                      color: f.color || valueColor(numVal),
                      fontSize: 18,
                      fontWeight: 600,
                    },
                  }}
                />
              </div>
            </Col>
          );
        })}
      </Row>
      {chartOption && (
        <div style={{ marginTop: 12 }}>
          <ReactECharts echarts={echarts} option={chartOption} style={{ height: 200 }} />
        </div>
      )}
    </Card>
  );
}
