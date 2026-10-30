import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useMarketMargin } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors, useTokens } from "../../styles/ui";

const { Text } = Typography;

function formatValue(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return `${value.toFixed(digits)}`;
}

function formatSigned(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export default function MarginTab() {
  const c = useColors();
  const t = useTokens();
  const { data, isLoading, isFetching, error, refetch } = useMarketMargin();
  const items = useMemo(() => data?.items || [], [data?.items]);
  const hasData = items.length > 0;
  const latest = items[items.length - 1];
  const prev = items[items.length - 2];
  const balanceChange = latest?.rzrqye != null && prev?.rzrqye != null
    ? latest.rzrqye - prev.rzrqye
    : null;

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "cross" },
        backgroundColor: c.cardBg,
        borderColor: c.border,
        borderWidth: 1,
        textStyle: { color: c.textPrimary, fontSize: 12 },
        extraCssText: "box-shadow: var(--c-shadow-md); border-radius: 8px;",
        formatter: (params: Array<{ seriesName: string; value: number; marker: string }>) => {
          if (!params || params.length === 0) return "";
          const dateStr = (params[0] as unknown as { axisValueLabel: string }).axisValueLabel;
          let content = `<div style="font-weight: 600; margin-bottom: 6px; color: ${c.textPrimary}">${dateStr}</div>`;
          params.forEach((item) => {
            const val = item.value != null ? item.value.toFixed(2) : "-";
            const isNet = item.seriesName === "融资净买入";
            const prefix = isNet && item.value > 0 ? "+" : "";
            content += `<div style="display: flex; justify-content: space-between; gap: 16px; margin: 3px 0;">
              <span>${item.marker} ${item.seriesName}</span>
              <strong style="font-family: var(--c-font-mono);">${prefix}${val} 亿元</strong>
            </div>`;
          });
          return content;
        },
      },
      legend: {
        type: "scroll",
        top: 8,
        right: 16,
        itemGap: 16,
        data: ["两融余额", "融资余额", "融券余额", "融资净买入"],
        textStyle: { color: c.textSecondary, fontSize: 12 },
      },
      grid: { left: 16, right: 20, top: 52, bottom: 52, containLabel: true },
      xAxis: {
        type: "category",
        data: items.map((item) => item.date),
        axisLabel: { color: c.textSecondary, hideOverlap: true },
        axisLine: { lineStyle: { color: c.border } },
      },
      yAxis: [
        {
          type: "value",
          name: "余额(亿元)",
          scale: true,
          axisLabel: { color: c.textSecondary },
          nameTextStyle: { color: c.textSecondary, fontSize: 11, padding: [0, 8, 0, 0] },
          splitLine: { lineStyle: { color: c.border, type: "dashed" } },
        },
        {
          type: "value",
          name: "净买入(亿元)",
          scale: true,
          axisLabel: { color: c.textSecondary },
          nameTextStyle: { color: c.textSecondary, fontSize: 11, padding: [0, 0, 0, 8] },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", start: 60, end: 100 },
        { type: "slider", height: 18, bottom: 8, borderColor: "transparent" },
      ],
      series: [
        {
          name: "两融余额",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rzrqye),
          itemStyle: { color: c.primary },
          lineStyle: { width: 3, color: c.primary },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(22, 119, 255, 0.16)" },
                { offset: 1, color: "rgba(22, 119, 255, 0.01)" },
              ],
            },
          },
        },
        {
          name: "融资余额",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rzye),
          itemStyle: { color: c.accent },
          lineStyle: { width: 2, color: c.accent },
        },
        {
          name: "融券余额",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rqye),
          itemStyle: { color: c.warning },
          lineStyle: { width: 1.5, color: c.warning, type: "dashed" },
        },
        {
          name: "融资净买入",
          type: "bar",
          yAxisIndex: 1,
          data: items.map((item) => item.rzjme),
          itemStyle: {
            color: (params: { value: number | null }) =>
              params.value != null && params.value < 0 ? c.down : c.up,
            opacity: 0.65,
            borderRadius: [2, 2, 0, 0],
          },
          barMaxWidth: 6,
        },
      ],
    }),
    [items, c.primary, c.accent, c.warning, c.up, c.down, c.textPrimary, c.textSecondary, c.border, c.cardBg],
  );

  return (
    <SectionDataState
      isLoading={isLoading && !hasData}
      error={hasData ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!isLoading && !error && !hasData}
      emptyText="暂无融资融券数据"
      errorTitle="融资融券数据加载失败"
      minHeight={420}
      skeletonRows={8}
    >
      <div className="market-margin">
        <Row gutter={[16, 16]} className="market-margin__metrics" style={{ marginBottom: t.space[4] }}>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="margin-total-balance" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>两融余额 (亿元)</span>}
                value={formatValue(latest?.rzrqye)}
                styles={{ content: { color: c.primary, fontWeight: Number(t.weight.bold), fontFamily: "var(--c-font-mono)" } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="margin-fin-balance" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>融资余额 (亿元)</span>}
                value={formatValue(latest?.rzye)}
                styles={{ content: { color: c.accent, fontWeight: Number(t.weight.bold), fontFamily: "var(--c-font-mono)" } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="margin-sec-balance" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>融券余额 (亿元)</span>}
                value={formatValue(latest?.rqye)}
                styles={{ content: { color: c.warning, fontWeight: Number(t.weight.bold), fontFamily: "var(--c-font-mono)" } }}
              />
            </Card>
          </Col>
          <Col xs={12} sm={6}>
            <Card size="small" data-testid="margin-balance-change" style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}>
              <Statistic
                title={<span style={{ color: c.textSecondary, fontSize: t.font.sm }}>两融日变动 (亿元)</span>}
                value={formatSigned(balanceChange)}
                styles={{ content: { color: (balanceChange ?? 0) >= 0 ? c.up : c.down, fontWeight: Number(t.weight.bold), fontFamily: "var(--c-font-mono)" } }}
              />
            </Card>
          </Col>
        </Row>

        <Card
          className="market-margin__chart-card"
          title={<span style={{ fontWeight: Number(t.weight.semibold) }}>沪深两市融资融券历史走势</span>}
          extra={
            <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
              刷新
            </Button>
          }
          style={{ borderRadius: t.radius.md, boxShadow: t.shadow.xs }}
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary" style={{ fontSize: t.font.sm }}>
              数据截至：{latest?.date || "-"}，单位：亿元，覆盖最近约一年交易日，柱状为融资净买入（右轴），支持拖拽缩放与区间筛选
            </Text>
          </div>
          <ReactECharts echarts={echarts} option={option} className="market-margin__chart" style={{ height: 460, width: "100%" }} notMerge />
        </Card>
      </div>
    </SectionDataState>
  );
}
