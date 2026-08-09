import { useMemo } from "react";
import { Card, Col, Descriptions, Empty, Row, Statistic, Table, Tag, Typography } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import type { QuantBacktestResult } from "../../api/queries";
import echarts from "../../charts/echarts-setup";
import { useMediaQuery } from "../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../styles/ui";

const { Text } = Typography;

function formatPercent(value?: number | null) {
  return value == null ? "-" : `${value.toFixed(2)}%`;
}

function formatNumber(value?: number | null) {
  return value == null ? "-" : value.toFixed(2);
}

export default function BacktestResult({ result }: { result: QuantBacktestResult }) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const metrics = result.metrics;
  const chartHeight = isNarrow ? 260 : 340;
  const equityOption = useMemo(() => ({
    tooltip: { trigger: "axis" },
    legend: {
      data: ["策略净值", "基准净值"],
      textStyle: { color: colors.textSecondary },
      itemWidth: isNarrow ? 18 : 25,
    },
    grid: {
      left: isNarrow ? 48 : 62,
      right: isNarrow ? 12 : 24,
      top: 42,
      bottom: isNarrow ? 32 : 42,
    },
    xAxis: {
      type: "category",
      data: result.equity_curve.map((point) => point.date),
      axisLabel: { color: colors.textMuted, hideOverlap: true },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { color: colors.textMuted },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [
      {
        name: "策略净值",
        type: "line",
        showSymbol: false,
        data: result.equity_curve.map((point) => point.equity),
        lineStyle: { color: colors.primary, width: 2 },
      },
      {
        name: "基准净值",
        type: "line",
        showSymbol: false,
        data: result.equity_curve.map((point) => point.benchmark),
        lineStyle: { color: colors.textMuted, type: "dashed" },
      },
    ],
  }), [colors, isNarrow, result.equity_curve]);
  const drawdownOption = useMemo(() => ({
    tooltip: { trigger: "axis", valueFormatter: (value: number) => `${value.toFixed(2)}%` },
    grid: {
      left: isNarrow ? 48 : 54,
      right: isNarrow ? 12 : 20,
      top: 20,
      bottom: isNarrow ? 32 : 38,
    },
    xAxis: {
      type: "category",
      data: result.equity_curve.map((point) => point.date),
      axisLabel: { color: colors.textMuted, hideOverlap: true },
      axisLine: { lineStyle: { color: colors.border } },
    },
    yAxis: {
      type: "value",
      max: 0,
      axisLabel: { formatter: "{value}%", color: colors.textMuted },
      splitLine: { lineStyle: { color: colors.border } },
    },
    series: [{
      name: "回撤",
      type: "line",
      showSymbol: false,
      areaStyle: { color: `${colors.down}30` },
      lineStyle: { color: colors.down },
      data: result.equity_curve.map((point) => point.drawdown * 100),
    }],
  }), [colors, isNarrow, result.equity_curve]);
  const metricItems = [
    ["总收益", metrics.total_return, "%"],
    ["年化收益", metrics.annualized_return, "%"],
    ["超额收益", metrics.excess_return, "%"],
    ["最大回撤", metrics.max_drawdown, "%"],
    ["夏普比率", metrics.sharpe_ratio, ""],
    ["胜率", metrics.win_rate, "%"],
  ] as const;

  return (
    <section aria-label="回测结果">
      <div className="quant-metric-grid">
        {metricItems.map(([label, value, suffix]) => (
          <Card size="small" style={cardStyle} className="quant-metric-card" key={label}>
            <Statistic
              title={label}
              value={value ?? "-"}
              precision={value == null ? undefined : 2}
              suffix={value == null ? undefined : suffix}
              styles={{
                content: {
                  color: label === "最大回撤"
                    ? colors.down
                    : typeof value === "number" && value > 0 ? colors.up : colors.textPrimary,
                },
              }}
            />
          </Card>
        ))}
      </div>

      <Card title="回测概览" size="small" style={cardStyle} className="quant-result-overview">
        <Descriptions
          size="small"
          bordered
          column={{ xs: 1, sm: 2, lg: 4 }}
          items={[
            { key: "benchmark", label: "基准收益", children: formatPercent(metrics.benchmark_return) },
            { key: "volatility", label: "年化波动", children: formatPercent(metrics.annualized_volatility) },
            { key: "turnover", label: "换手率", children: formatPercent(metrics.turnover_rate) },
            { key: "trades", label: "交易次数", children: `${metrics.trade_count} 次` },
            { key: "profit-loss", label: "盈亏比", children: formatNumber(metrics.profit_loss_ratio) },
            { key: "codes", label: "股票池", children: result.codes.join("、") || "-" },
            { key: "sources", label: "数据来源", children: result.data_sources.join("、") || "-" },
            { key: "engine", label: "引擎版本", children: result.engine_version || "-" },
          ]}
        />
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} xl={15}>
          <Card title="策略与基准净值" size="small" style={cardStyle}>
            {result.equity_curve.length > 0 ? (
              <ReactECharts
                echarts={echarts}
                option={equityOption}
                style={{ height: chartHeight }}
                notMerge
                data-testid="equity-chart"
              />
            ) : <div className="quant-chart-empty"><Empty description="暂无净值数据" /></div>}
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card title="组合回撤" size="small" style={cardStyle}>
            {result.equity_curve.length > 0 ? (
              <ReactECharts
                echarts={echarts}
                option={drawdownOption}
                style={{ height: chartHeight }}
                notMerge
                data-testid="drawdown-chart"
              />
            ) : <div className="quant-chart-empty"><Empty description="暂无回撤数据" /></div>}
          </Card>
        </Col>
      </Row>

      <Row gutter={[16, 16]}>
        <Col xs={24} xl={8}>
          <Card title="月度收益" size="small" style={cardStyle} className="quant-table-card">
            <Table
              size="small"
              rowKey="month"
              pagination={result.monthly_returns.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
              dataSource={result.monthly_returns}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无月度收益" /> }}
              columns={[
                { title: "月份", dataIndex: "month" },
                {
                  title: "收益率",
                  dataIndex: "return_pct",
                  align: "right",
                  render: (value: number) => (
                    <Text style={{ color: value >= 0 ? colors.up : colors.down }}>{formatPercent(value)}</Text>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={16}>
          <Card
            title="成交记录"
            extra={<Tag>{result.trades.length} 笔</Tag>}
            size="small"
            style={cardStyle}
            className="quant-table-card"
          >
            <Table
              size="small"
              rowKey={(trade) => `${trade.date}-${trade.code}-${trade.side}-${trade.shares}`}
              scroll={{ x: 760 }}
              pagination={result.trades.length > 8 ? { pageSize: 8, size: "small", showSizeChanger: false } : false}
              dataSource={result.trades}
              locale={{ emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无成交记录" /> }}
              columns={[
                { title: "日期", dataIndex: "date", width: 110 },
                { title: "代码", dataIndex: "code", width: 90 },
                {
                  title: "方向",
                  dataIndex: "side",
                  width: 70,
                  render: (side: string) => <Tag color={side === "buy" ? "red" : "green"}>{side === "buy" ? "买入" : "卖出"}</Tag>,
                },
                { title: "价格", dataIndex: "price", align: "right", render: (value: number) => value.toFixed(2) },
                { title: "股数", dataIndex: "shares", align: "right" },
                { title: "费用", dataIndex: "fee", align: "right", render: (value: number) => value.toFixed(2) },
                {
                  title: "实现盈亏",
                  dataIndex: "realized_pnl",
                  align: "right",
                  render: (value?: number | null) => value == null ? "-" : (
                    <Text style={{ color: value >= 0 ? colors.up : colors.down }}>{value.toFixed(2)}</Text>
                  ),
                },
              ]}
            />
          </Card>
        </Col>
      </Row>
    </section>
  );
}
