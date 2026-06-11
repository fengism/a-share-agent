import { useMemo } from "react";
import ReactECharts from "echarts-for-react";
import { Card, Col, Empty, Row, Statistic, Typography } from "antd";
import { useStyles, darkColors } from "../../styles/ui";;

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
}

function valueColor(value: number | null | undefined) {
  if (value == null) return darkColors.textSecondary;
  if (value > 0) return darkColors.up;
  if (value < 0) return darkColors.down;
  return darkColors.textSecondary;
}

export default function MacroIndicatorCard({
  title,
  latest,
  trend,
  fields,
  dateKey = "TIME",
  chartType = "line",
}: MacroIndicatorCardProps) {
  const { cardStyle } = useStyles();
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
        lineStyle: { width: 2, color: f.color || darkColors.primary },
        itemStyle: { color: f.color || darkColors.primary },
      }));

    return {
      tooltip: { trigger: "axis" },
      legend: {
        data: fields.map((f) => f.label),
        textStyle: { color: darkColors.textSecondary, fontSize: 11 },
        top: 4,
      },
      grid: { left: 48, right: 16, top: 36, bottom: 28 },
      xAxis: {
        type: "category",
        data: dates,
        axisLabel: { color: darkColors.textMuted, fontSize: 10, rotate: 30 },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: darkColors.textMuted, fontSize: 10 },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.12)" } },
      },
      series,
    };
  }, [trend, fields, dateKey, chartType]);

  if (!latest || fields.length === 0) {
    return (
      <Card style={{ ...cardStyle, minHeight: 200 }}>
        <Text style={{ color: darkColors.textSecondary }}>{title} 暂无数据</Text>
        <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="数据加载中或暂不可用" />
      </Card>
    );
  }

  const dateValue = latest[dateKey];

  return (
    <Card
      style={cardStyle}
      title={
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <span style={{ color: darkColors.textPrimary, fontWeight: 600 }}>{title}</span>
          {dateValue && (
            <Text style={{ color: darkColors.textMuted, fontSize: 12 }}>{String(dateValue)}</Text>
          )}
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
                <Text style={{ color: darkColors.textMuted, fontSize: 11, display: "block", marginBottom: 2 }}>
                  {f.label}
                </Text>
                <Statistic
                  value={numVal ?? undefined}
                  precision={numVal != null ? precision : undefined}
                  suffix={f.unit}
                  valueStyle={{
                    color: f.color || valueColor(numVal),
                    fontSize: 18,
                    fontWeight: 600,
                  }}
                />
              </div>
            </Col>
          );
        })}
      </Row>
      {chartOption && (
        <div style={{ marginTop: 12 }}>
          <ReactECharts option={chartOption} style={{ height: 200 }} />
        </div>
      )}
    </Card>
  );
}
