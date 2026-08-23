import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useMarketMargin } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";

const { Text } = Typography;

function formatValue(value: number | null | undefined, digits = 2) {
  if (value == null) return "-";
  return `${value >= 0 ? "" : ""}${value.toFixed(digits)}`;
}

function formatSigned(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export default function MarginTab() {
  const c = useColors();
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
      },
      legend: {
        type: "scroll",
        top: 0,
        data: ["两融余额", "融资余额", "融券余额", "融资净买入"],
        textStyle: { color: c.textSecondary },
      },
      grid: { left: 12, right: 12, top: 72, bottom: 56, containLabel: true },
      xAxis: {
        type: "category",
        data: items.map((item) => item.date),
        axisLabel: { color: c.textSecondary, hideOverlap: true },
      },
      yAxis: [
        {
          type: "value",
          name: "余额(亿元)",
          scale: true,
          axisLabel: { color: c.textSecondary },
          splitLine: { lineStyle: { color: c.border } },
        },
        {
          type: "value",
          name: "净买入(亿元)",
          axisLabel: { color: c.textSecondary },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", start: 60, end: 100 },
        { type: "slider", height: 18, bottom: 8 },
      ],
      series: [
        {
          name: "两融余额",
          type: "line",
          smooth: true,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rzrqye),
          itemStyle: { color: c.primary },
          lineStyle: { width: 3, color: c.primary },
        },
        {
          name: "融资余额",
          type: "line",
          smooth: true,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rzye),
          itemStyle: { color: c.accent },
          lineStyle: { width: 2, color: c.accent },
        },
        {
          name: "融券余额",
          type: "line",
          smooth: true,
          showSymbol: false,
          yAxisIndex: 0,
          data: items.map((item) => item.rqye),
          itemStyle: { color: c.warning },
          lineStyle: { width: 1.5, color: c.warning },
        },
        {
          name: "融资净买入",
          type: "bar",
          yAxisIndex: 1,
          data: items.map((item) => item.rzjme),
          itemStyle: {
            color: (params: { value: number | null }) =>
              params.value != null && params.value < 0 ? c.down : c.up,
            opacity: 0.55,
          },
          barMaxWidth: 6,
        },
      ],
    }),
    [items, c.primary, c.accent, c.warning, c.up, c.down, c.textSecondary, c.border],
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
        <Row gutter={[16, 16]} className="market-margin__metrics">
          <Col xs={24} md={6}>
            <Card data-testid="margin-total-balance">
              <Statistic title="两融余额(亿元)" value={formatValue(latest?.rzrqye)} styles={{ content: { color: c.textPrimary } }} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card data-testid="margin-fin-balance">
              <Statistic title="融资余额(亿元)" value={formatValue(latest?.rzye)} styles={{ content: { color: c.accent } }} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card data-testid="margin-sec-balance">
              <Statistic title="融券余额(亿元)" value={formatValue(latest?.rqye)} styles={{ content: { color: c.warning } }} />
            </Card>
          </Col>
          <Col xs={24} md={6}>
            <Card data-testid="margin-balance-change">
              <Statistic title="两融余额日变动(亿元)" value={formatSigned(balanceChange)} styles={{ content: { color: (balanceChange ?? 0) >= 0 ? c.up : c.down } }} />
            </Card>
          </Col>
        </Row>

        <Card
          className="market-margin__chart-card"
          title="沪深两市融资融券历史走势"
          extra={
            <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
              刷新
            </Button>
          }
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary">
              数据截至：{latest?.date || "-"}，单位：亿元，覆盖最近约一年交易日，柱状为融资净买入（右轴），可拖动缩放查看区间
            </Text>
          </div>
          <ReactECharts echarts={echarts} option={option} className="market-margin__chart" style={{ height: 460, width: "100%" }} notMerge />
        </Card>
      </div>
    </SectionDataState>
  );
}
