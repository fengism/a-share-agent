import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useMarketBreadth } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens } from "../../styles/ui";

const { Text } = Typography;

function formatPct(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value.toFixed(1)}%`;
}

function breadthState(ratio: number | null | undefined): string {
  if (ratio == null) return "-";
  if (ratio >= 70) return "全面强势";
  if (ratio >= 50) return "偏强运行";
  if (ratio >= 30) return "分化震荡";
  return "情绪低迷 / 调整末期";
}

export default function MarketBreadthTab() {
  const c = useColors();
  const t = useTokens();
  const { data, isLoading, isFetching, error, refetch } = useMarketBreadth();
  const industries = useMemo(() => data?.industries || [], [data?.industries]);
  const dates = useMemo(() => data?.dates || [], [data?.dates]);
  const values = useMemo(() => data?.values || [], [data?.values]);
  const summaries = useMemo(() => data?.summaries || [], [data?.summaries]);
  const lastSummary = summaries[summaries.length - 1];
  const hasData = dates.length > 0 && industries.length > 0;

  const heatmapData = useMemo(() => {
    const rows: Array<[number, number, number | null]> = [];
    values.forEach((row, y) => {
      row.forEach((value, x) => {
        if (value != null) {
          rows.push([x, y, value]);
        }
      });
    });
    return rows;
  }, [values]);

  const option = useMemo(
    () => ({
      tooltip: {
        position: "top",
        backgroundColor: "rgba(255, 255, 255, 0.95)",
        borderColor: c.border,
        borderWidth: 1,
        textStyle: { color: c.textPrimary, fontSize: 12 },
        extraCssText: "box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08); border-radius: 8px;",
        formatter: (params: { data: [number, number, number | null] }) => {
          const [x, y, value] = params.data;
          const dateStr = dates[x] || "-";
          const industry = industries[y] || "-";
          return `<div style="font-weight: 600; color: ${c.textPrimary}">${industry}</div>
            <div style="margin-top: 4px;">${dateStr}：<strong style="font-family: var(--c-font-mono);">${value == null ? "-" : value.toFixed(1)}%</strong></div>`;
        },
      },
      grid: { left: 14, right: 12, top: 8, bottom: 58, containLabel: true },
      xAxis: {
        type: "category",
        data: dates,
        splitArea: { show: true },
        axisLabel: { color: c.textSecondary, hideOverlap: true, fontSize: 11 },
        axisLine: { lineStyle: { color: c.border } },
      },
      yAxis: {
        type: "category",
        data: industries,
        axisLabel: { color: c.textSecondary, fontSize: 11 },
        splitArea: { show: true },
        axisLine: { lineStyle: { color: c.border } },
      },
      visualMap: {
        min: 0,
        max: 100,
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 4,
        textStyle: { color: c.textSecondary, fontSize: 11 },
        inRange: { color: ["#1d39c4", "#f5222d"] },
      },
      dataZoom: [
        { type: "inside", xAxisIndex: 0 },
        { type: "slider", xAxisIndex: 0, height: 18, bottom: 26, borderColor: "transparent" },
      ],
      series: [
        {
          name: "市场宽度",
          type: "heatmap",
          data: heatmapData,
          label: { show: false },
          emphasis: { itemStyle: { shadowBlur: 10, shadowColor: "rgba(0, 0, 0, 0.5)" } },
        },
      ],
    }),
    [heatmapData, dates, industries, c.textPrimary, c.textSecondary, c.border],
  );

  return (
    <SectionDataState
      isLoading={isLoading && !hasData}
      error={hasData ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!isLoading && !error && !hasData}
      emptyText="暂无市场宽度数据"
      errorTitle="市场宽度数据加载失败"
      minHeight={420}
      skeletonRows={8}
    >
      <div className="market-breadth">
        <Row gutter={[16, 16]} className="market-breadth__metrics" style={{ marginBottom: t.space[4] }}>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="breadth-latest-date" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>统计日期</span>}
                value={lastSummary?.date || "-"}
                styles={{ content: { color: c.textPrimary, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="breadth-strong-ratio" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>强势行业占比 (宽&gt;50%)</span>}
                value={formatPct(lastSummary?.strong_ratio)}
                styles={{ content: { color: (lastSummary?.strong_ratio ?? 0) >= 50 ? c.up : c.down, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="breadth-strong-count" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>强势行业数</span>}
                value={lastSummary
                  ? `${lastSummary.strong_industry_count} / ${lastSummary.total_industry_count}`
                  : "-"}
                styles={{ content: { color: c.textPrimary, fontWeight: Number(t.weight.bold) } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="breadth-state" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>市场状态</span>}
                value={breadthState(lastSummary?.strong_ratio)}
                styles={{ content: { color: c.primary, fontWeight: Number(t.weight.bold), fontSize: t.font.md } }}
              />
            </Card>
          </Col>
        </Row>

        <Card
          className="market-breadth__chart-card"
          title={<span style={{ fontWeight: Number(t.weight.semibold) }}>申万2级行业市场宽度热力图</span>}
          extra={
            <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
              刷新
            </Button>
          }
          style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: t.font.sm }}>
              数据截至：{lastSummary?.date || "-"}；颜色越红代表行业中站上 MA20 的股票越多（行业短期趋势越强），越蓝代表行业整体偏弱；超过 70% 的行业处于较高宽度表明市场全面强势，低于 30% 则为市场调整末期、情绪低迷
            </Text>
          </div>
          <ReactECharts echarts={echarts} option={option} className="market-breadth__chart" style={{ height: 520, width: "100%" }} notMerge />
        </Card>
      </div>
    </SectionDataState>
  );
}
