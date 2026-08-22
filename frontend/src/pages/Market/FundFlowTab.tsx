import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useHsgtFlow } from "../../api/queries";
import SectionDataState from "../../components/SectionDataState";
import { useColors } from "../../styles/ui";
import "./market-fund-flow.css";

const { Text } = Typography;

function formatYi(value: number | null | undefined) {
  if (value == null) return "-";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;
}

export default function FundFlowTab() {
  const c = useColors();
  const northboundColor = c.warning;
  const shanghaiColor = c.up;
  const shenzhenColor = c.down;
  const { data, isLoading, isFetching, error, refetch } = useHsgtFlow();
  const points = useMemo(() => data?.points || [], [data?.points]);
  const hasData = points.length > 0;
  const latest = points[points.length - 1];
  const hgtPointCount = points.filter((item) => item.hgt != null).length;
  const sgtPointCount = points.filter((item) => item.sgt != null).length;

  const option = useMemo(
    () => ({
      tooltip: { trigger: "axis" },
      legend: {
        type: "scroll",
        data: ["北向合计", "沪股通", "深股通"],
        textStyle: { color: c.textSecondary },
      },
      grid: { left: 12, right: 16, top: 56, bottom: 20, containLabel: true },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((item) => item.time),
        axisLabel: { color: c.textSecondary, hideOverlap: true },
      },
      yAxis: {
        type: "value",
        name: data?.unit || "亿元",
        axisLabel: { color: c.textSecondary },
        splitLine: { lineStyle: { color: c.border } },
      },
      series: [
        {
          name: "北向合计",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.total),
          connectNulls: true,
          itemStyle: { color: northboundColor },
          lineStyle: { width: 3, color: northboundColor },
        },
        {
          name: "沪股通",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.hgt),
          connectNulls: true,
          itemStyle: { color: shanghaiColor },
          lineStyle: { width: 2, color: shanghaiColor },
        },
        {
          name: "深股通",
          type: "line",
          smooth: true,
          showSymbol: false,
          data: points.map((item) => item.sgt),
          connectNulls: true,
          itemStyle: { color: shenzhenColor },
          lineStyle: { width: 2, color: shenzhenColor },
        },
      ],
    }),
    [data?.unit, points, shanghaiColor, shenzhenColor, c.textSecondary, c.border, northboundColor],
  );

  return (
    <SectionDataState
      isLoading={isLoading && !hasData}
      error={hasData ? undefined : error}
      onRetry={() => refetch()}
      isEmpty={!isLoading && !error && !hasData}
      emptyText="暂无北向资金分钟流向数据"
      errorTitle="北向资金分钟流向加载失败"
      minHeight={420}
      skeletonRows={8}
    >
      <div className="market-fund-flow">
        <Row gutter={[16, 16]} className="market-fund-flow__metrics">
          <Col xs={24} md={8}>
            <Card data-testid="northbound-total">
              <Statistic title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: northboundColor }} />北向合计净买入</span>} value={formatYi(latest?.total)} suffix={data?.unit || "亿元"} styles={{ content: { color: northboundColor } }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card data-testid="northbound-shanghai">
              <Statistic title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: shanghaiColor }} />沪股通净买入</span>} value={formatYi(latest?.hgt)} suffix={data?.unit || "亿元"} styles={{ content: { color: shanghaiColor } }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card data-testid="northbound-shenzhen">
              <Statistic title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: shenzhenColor }} />深股通净买入</span>} value={formatYi(latest?.sgt)} suffix={data?.unit || "亿元"} styles={{ content: { color: shenzhenColor } }} />
            </Card>
          </Col>
        </Row>

        <Card
          className="market-fund-flow__chart-card"
          title="北向资金实时流向"
          extra={
            <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
              刷新
            </Button>
          }
        >
          <div style={{ marginBottom: 12 }}>
            <Text type="secondary">
              更新时间：{data?.updated_at || "-"}，单位：{data?.unit || "亿元"}，自动刷新：交易时段每 60 秒，盘外暂停，可手动刷新
            </Text>
            <Text type="secondary" className="market-fund-flow__disclosure-note">
              数据源：同花顺 data.hexin.cn 原始接口；沪股通 {hgtPointCount}/{points.length} 点，深股通 {sgtPointCount}/{points.length} 点，缺失数据不补造。
            </Text>
          </div>
          <ReactECharts echarts={echarts} option={option} className="market-fund-flow__chart" style={{ height: 420, width: "100%" }} notMerge />
        </Card>
      </div>
    </SectionDataState>
  );
}
