import { useEffect, useMemo, useState } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useHsgtFlow } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import type { ThemeColors } from "../../styles/ui";

const { Text } = Typography;

function isAutoRefreshTime(now = new Date()) {
  const minutes = now.getHours() * 60 + now.getMinutes();
  return minutes >= 9 * 60 + 20 && minutes <= 15 * 60 + 30;
}

function formatYi(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

function valueColor(value: number | null | undefined, c: ThemeColors) {
  if (value == null) return c.textSecondary;
  if (value > 0) return c.up;
  if (value < 0) return c.down;
  return c.textSecondary;
}

export default function FundFlowTab() {
  const c = useColors();
  const [autoRefresh, setAutoRefresh] = useState(() => isAutoRefreshTime());

  useEffect(() => {
    const timer = window.setInterval(() => setAutoRefresh(isAutoRefreshTime()), 60 * 1000);
    return () => window.clearInterval(timer);
  }, []);

  const { data, isLoading, isFetching, error, refetch } = useHsgtFlow(true, autoRefresh);
  const points = useMemo(() => data?.points || [], [data?.points]);
  const hasData = points.length > 0;
  const latest = points[points.length - 1];

  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: { data: ["合计", "沪股通", "深股通"], textStyle: { color: c.textSecondary } },
      grid: { left: 48, right: 24, top: 48, bottom: 36 },
      xAxis: { type: "category", data: points.map((item) => item.time), axisLabel: { color: c.textSecondary } },
      yAxis: {
        type: "value",
        name: data?.unit || "亿元",
        axisLabel: { color: c.textSecondary },
        splitLine: { lineStyle: { color: "rgba(148,163,184,0.15)" } },
      },
      series: [
        {
          name: "合计",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.total),
          lineStyle: { width: 3, color: "#f59e0b" },
        },
        {
          name: "沪股通",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.hgt),
          lineStyle: { width: 2, color: c.up },
        },
        {
          name: "深股通",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.sgt),
          lineStyle: { width: 2, color: c.primary },
        },
      ],
    }),
    [data?.unit, points, c.primary, c.textSecondary, c.up],
  );

  return (
    <SectionDataState
      isLoading={isLoading && !hasData}
      error={hasData ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!isLoading && !error && !hasData}
      emptyText="暂无沪深股通分钟流向数据"
      errorTitle="沪深股通分钟流向加载失败"
      minHeight={420}
      skeletonRows={8}
    >
      <div>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} md={8}>
            <Card style={{ borderRadius: 8 }}>
              <Statistic title="北向合计净买入" value={formatYi(latest?.total)} suffix={data?.unit || "亿元"} valueStyle={{ color: valueColor(latest?.total, c) }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card style={{ borderRadius: 8 }}>
              <Statistic title="沪股通净买入" value={formatYi(latest?.hgt)} suffix={data?.unit || "亿元"} valueStyle={{ color: valueColor(latest?.hgt, c) }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card style={{ borderRadius: 8 }}>
              <Statistic title="深股通净买入" value={formatYi(latest?.sgt)} suffix={data?.unit || "亿元"} valueStyle={{ color: valueColor(latest?.sgt, c) }} />
            </Card>
          </Col>
        </Row>

        <Card
          title="沪深股通当日实时分钟流向"
          extra={
            <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
              刷新
            </Button>
          }
          style={{ borderRadius: 8 }}
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary">
              更新时间：{data?.updated_at || "-"}，单位：{data?.unit || "亿元"}，自动刷新：{autoRefresh ? "09:20–15:30 每 60 秒" : "已暂停，可手动刷新"}
            </Text>
          </div>
          <ReactECharts echarts={echarts} option={option} style={{ height: 420 }} notMerge />
        </Card>
      </div>
    </SectionDataState>
  );
}
