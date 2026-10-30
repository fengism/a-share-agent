import { useMemo } from "react";
import ReactECharts from "echarts-for-react/lib/core";
import echarts from "../../charts/echarts-setup";
import { Button, Card, Col, Row, Statistic, Typography } from "antd";
import { ReloadOutlined } from "@ant-design/icons";
import { useHsgtFlow, useNorthboundHistory } from "../../api/queries";
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
  const hs300Color = c.primary;
  const realtimeQuery = useHsgtFlow();
  const historyQuery = useNorthboundHistory(500);

  const points = useMemo(() => realtimeQuery.data?.points || [], [realtimeQuery.data?.points]);
  const hasData = points.length > 0;
  const latest = points[points.length - 1];
  const hgtPointCount = points.filter((item) => item.hgt != null).length;
  const sgtPointCount = points.filter((item) => item.sgt != null).length;
  const historyItems = useMemo(() => historyQuery.data?.items || [], [historyQuery.data?.items]);
  const hasHistory = historyItems.length > 0;

  const option = useMemo(
    () => ({
      tooltip: {
        trigger: "axis",
        backgroundColor: c.cardBg,
        borderColor: c.border,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: c.textPrimary, fontSize: 12 },
        extraCssText: "box-shadow: var(--c-shadow-md); border-radius: 8px;",
        formatter: (params: Array<{ axisValue: string; color: string; seriesName: string; value: number | null }>) => {
          if (!params || params.length === 0) return "";
          const header = `<div style="font-weight: 600; margin-bottom: 6px; color: ${c.textPrimary};">${params[0].axisValue}</div>`;
          const rows = params.map((p) => {
            const val = p.value != null ? `${Number(p.value) >= 0 ? "+" : ""}${Number(p.value).toFixed(2)} ${realtimeQuery.data?.unit || "亿元"}` : "-";
            const valColor = p.value != null ? (Number(p.value) >= 0 ? c.up : c.down) : c.textSecondary;
            return `<div style="display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 3px 0;">
              <span style="display: inline-flex; align-items: center; gap: 6px;">
                <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: ${p.color};"></span>
                <span>${p.seriesName}</span>
              </span>
              <span style="font-weight: 600; font-family: var(--c-font-mono); color: ${valColor};">${val}</span>
            </div>`;
          });
          return header + rows.join("");
        },
      },
      legend: {
        type: "scroll",
        top: 8,
        right: 16,
        itemGap: 18,
        icon: "roundRect",
        itemWidth: 14,
        itemHeight: 8,
        data: ["北向合计", "沪股通", "深股通"],
        textStyle: { color: c.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 16,
        right: 20,
        top: 48,
        bottom: 24,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: points.map((item) => item.time),
        axisLine: { lineStyle: { color: c.border } },
        axisTick: { show: false },
        axisLabel: {
          color: c.textSecondary,
          hideOverlap: true,
          margin: 10,
        },
      },
      yAxis: {
        type: "value",
        name: realtimeQuery.data?.unit || "亿元",
        nameLocation: "end",
        nameTextStyle: {
          color: c.textSecondary,
          fontSize: 11,
          padding: [0, 24, 0, 0],
        },
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: {
          color: c.textSecondary,
          formatter: (v: number) => `${v >= 0 ? "+" : ""}${v}`,
        },
        splitLine: {
          lineStyle: { color: c.border, type: "dashed" },
        },
      },
      dataZoom: [
        {
          type: "inside",
          start: 0,
          end: 100,
        },
      ],
      series: [
        {
          name: "北向合计",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          data: points.map((item) => item.total),
          connectNulls: true,
          itemStyle: { color: northboundColor },
          lineStyle: { width: 3, color: northboundColor },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(247, 144, 9, 0.22)" },
                { offset: 1, color: "rgba(247, 144, 9, 0.01)" },
              ],
            },
          },
          markLine: {
            silent: true,
            symbol: "none",
            lineStyle: { color: c.border, type: "dashed", width: 1 },
            data: [{ yAxis: 0 }],
            label: { show: false },
          },
        },
        {
          name: "沪股通",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          data: points.map((item) => item.hgt),
          connectNulls: true,
          itemStyle: { color: shanghaiColor },
          lineStyle: { width: 2, color: shanghaiColor },
        },
        {
          name: "深股通",
          type: "line",
          smooth: 0.3,
          showSymbol: false,
          data: points.map((item) => item.sgt),
          connectNulls: true,
          itemStyle: { color: shenzhenColor },
          lineStyle: { width: 2, color: shenzhenColor },
        },
      ],
    }),
    [realtimeQuery.data?.unit, points, shanghaiColor, shenzhenColor, c, northboundColor],
  );

  const historyOption = useMemo(
    () => ({
      tooltip: {
        trigger: "axis",
        backgroundColor: c.cardBg,
        borderColor: c.border,
        borderWidth: 1,
        padding: [10, 14],
        textStyle: { color: c.textPrimary, fontSize: 12 },
        extraCssText: "box-shadow: var(--c-shadow-md); border-radius: 8px;",
        formatter: (params: Array<{ axisValue: string; color: string; seriesName: string; value: number | null }>) => {
          if (!params || params.length === 0) return "";
          const header = `<div style="font-weight: 600; margin-bottom: 6px; color: ${c.textPrimary};">${params[0].axisValue}</div>`;
          const rows = params.map((item) => {
            const value = item.value == null ? "-" : Number(item.value).toFixed(2);
            const unit = item.seriesName === "北向成交总额" ? historyQuery.data?.unit || "亿元" : "点";
            return `<div style="display: flex; justify-content: space-between; gap: 16px; margin: 3px 0;">
              <span><i style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};margin-right:6px;"></i><span style="color:${c.textSecondary};">${item.seriesName}</span></span>
              <strong style="font-family:var(--c-font-mono);color:${c.textPrimary};">${value} ${unit}</strong>
            </div>`;
          });
          return header + rows.join("");
        },
      },
      legend: {
        top: 8,
        right: 16,
        itemGap: 18,
        icon: "roundRect",
        itemWidth: 14,
        itemHeight: 8,
        data: ["北向成交总额", "沪深300"],
        textStyle: { color: c.textSecondary, fontSize: 12 },
      },
      grid: {
        left: 16,
        right: 16,
        top: 54,
        bottom: 52,
        containLabel: true,
      },
      xAxis: {
        type: "category",
        boundaryGap: false,
        data: historyItems.map((item) => item.date),
        axisLine: { lineStyle: { color: c.border } },
        axisTick: { show: false },
        axisLabel: { color: c.textSecondary, hideOverlap: true, margin: 10 },
      },
      yAxis: [
        {
          type: "value",
          name: historyQuery.data?.unit || "亿元",
          axisLabel: {
            color: c.textSecondary,
            formatter: (value: number) => `${value >= 0 ? "+" : ""}${value}`,
          },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { lineStyle: { color: c.border, type: "dashed" } },
        },
        {
          type: "value",
          name: `${historyQuery.data?.index_name || "沪深300"}（点）`,
          axisLabel: { color: c.textSecondary },
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
        },
      ],
      dataZoom: [
        { type: "inside", start: Math.max(0, 100 - (120 / Math.max(historyItems.length, 1)) * 100), end: 100 },
        {
          type: "slider",
          height: 18,
          bottom: 8,
          start: Math.max(0, 100 - (120 / Math.max(historyItems.length, 1)) * 100),
          end: 100,
          borderColor: "transparent",
          textStyle: { color: c.textSecondary },
        },
      ],
      series: [
        {
          name: "北向成交总额",
          type: "bar",
          yAxisIndex: 0,
          data: historyItems.map((item) => item.north_money),
          itemStyle: { color: northboundColor, borderRadius: [3, 3, 0, 0] },
          lineStyle: { color: northboundColor },
        },
        {
          name: "沪深300",
          type: "line",
          yAxisIndex: 1,
          smooth: 0.2,
          showSymbol: false,
          connectNulls: true,
          data: historyItems.map((item) => item.hs300_close),
          itemStyle: { color: hs300Color },
          lineStyle: { width: 2, color: hs300Color },
        },
      ],
    }),
    [c, historyItems, historyQuery.data?.index_name, historyQuery.data?.unit, hs300Color, northboundColor],
  );

  return (
    <div className="market-fund-flow">
      <SectionDataState
        isLoading={realtimeQuery.isLoading && !hasData}
        error={hasData ? undefined : realtimeQuery.error}
        onRetry={() => realtimeQuery.refetch()}
        isEmpty={!realtimeQuery.isLoading && !realtimeQuery.error && !hasData}
        emptyText="暂无北向资金分钟流向数据"
        errorTitle="北向资金分钟流向加载失败"
        minHeight={420}
        skeletonRows={8}
      >
        <div className="market-fund-flow__section">
          <Row gutter={[16, 16]} className="market-fund-flow__metrics">
            <Col xs={24} sm={8}>
              <Card data-testid="northbound-total">
                <Statistic
                  title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: northboundColor }} />北向合计净流入（数据商口径）</span>}
                  value={formatYi(latest?.total)}
                  suffix={realtimeQuery.data?.unit || "亿元"}
                  styles={{ content: { color: northboundColor } }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8}>
              <Card data-testid="northbound-shanghai">
                <Statistic
                  title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: shanghaiColor }} />沪股通净流入</span>}
                  value={formatYi(latest?.hgt)}
                  suffix={realtimeQuery.data?.unit || "亿元"}
                  styles={{ content: { color: shanghaiColor } }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={8}>
              <Card data-testid="northbound-shenzhen">
                <Statistic
                  title={<span className="market-fund-flow__metric-title"><i style={{ backgroundColor: shenzhenColor }} />深股通净流入</span>}
                  value={formatYi(latest?.sgt)}
                  suffix={realtimeQuery.data?.unit || "亿元"}
                  styles={{ content: { color: shenzhenColor } }}
                />
              </Card>
            </Col>
          </Row>

          <Card
            className="market-fund-flow__chart-card"
            title={realtimeQuery.data?.is_stale ? "最近交易日北向资金流向" : "北向资金实时流向"}
            extra={
              <Button icon={<ReloadOutlined />} loading={realtimeQuery.isFetching} onClick={() => realtimeQuery.refetch()}>
                刷新
              </Button>
            }
          >
            <div style={{ marginBottom: 12 }}>
              <Text type="secondary">
                数据日期：{realtimeQuery.data?.date || "-"}，更新时间：{realtimeQuery.data?.updated_at || "-"}，单位：{realtimeQuery.data?.unit || "亿元"}，自动刷新：交易时段每 60 秒，盘外暂停，可手动刷新
              </Text>
              {realtimeQuery.data?.is_stale ? (
                <Text type="warning" className="market-fund-flow__disclosure-note">
                  当前展示最近一次本地数据。
                </Text>
              ) : null}
              <Text type="secondary" className="market-fund-flow__disclosure-note">
                沪股通 {hgtPointCount}/{points.length} 点，深股通 {sgtPointCount}/{points.length} 点，缺失数据不补造。
              </Text>
            </div>
            <ReactECharts echarts={echarts} option={option} className="market-fund-flow__chart" style={{ height: 420, width: "100%" }} notMerge />
          </Card>
        </div>
      </SectionDataState>

      <SectionDataState
        isLoading={historyQuery.isLoading && !hasHistory}
        error={hasHistory ? undefined : historyQuery.error}
        onRetry={() => historyQuery.refetch()}
        isEmpty={!historyQuery.isLoading && !historyQuery.error && !hasHistory}
        emptyText="暂无北向资金历史数据"
        errorTitle="北向资金历史走势加载失败"
        minHeight={420}
        skeletonRows={8}
      >
        <Card
          className="market-fund-flow__chart-card"
          title="北向成交总额与沪深300走势"
          extra={
            <Button icon={<ReloadOutlined />} loading={historyQuery.isFetching} onClick={() => historyQuery.refetch()}>
              刷新
            </Button>
          }
        >
          <div className="market-fund-flow__history-meta">
            <Text type="secondary">
              数据来源：{historyQuery.data?.source || "乐咕乐股"}，更新时间：{historyQuery.data?.updated_at || "-"}，北向资金单位：{historyQuery.data?.unit || "亿元"}
            </Text>
            {historyQuery.data?.is_stale ? (
              <Text type="warning" className="market-fund-flow__disclosure-note">
                上游刷新失败，当前展示最近一次本地快照。
              </Text>
            ) : null}
          </div>
          <ReactECharts echarts={echarts} option={historyOption} className="market-fund-flow__chart" style={{ height: 440, width: "100%" }} notMerge />
        </Card>
      </SectionDataState>
    </div>
  );
}
