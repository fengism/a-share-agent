import { useMemo, useState } from "react";
import { AppstoreOutlined, AreaChartOutlined, InfoCircleOutlined, LineChartOutlined, PieChartOutlined } from "@ant-design/icons";
import { Card, Col, Empty, Row, Segmented, Tooltip } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import type { QuantBacktestResult } from "../../../api/queries";
import echarts from "../../../charts/echarts-setup";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../../styles/ui";
import {
  buildAlphaRiskChartOption,
  buildDrawdownChartOption,
  buildEquityChartOption,
  buildHoldingsAllocationChartOption,
} from "./backtestChartOptions";

interface BacktestChartsProps {
  equityCurve: QuantBacktestResult["equity_curve"];
}

const VIEW_OPTIONS = [
  { label: "全部走势", value: "all", icon: <AppstoreOutlined /> },
  { label: "净值与回撤", value: "nav", icon: <LineChartOutlined /> },
  { label: "动态持仓演变", value: "holdings", icon: <PieChartOutlined /> },
  { label: "超额与滚动风险", value: "alpha", icon: <AreaChartOutlined /> },
];

export default function BacktestCharts({ equityCurve }: BacktestChartsProps) {
  const [chartView, setChartView] = useState<string>("all");
  const colors = useColors();
  const { cardStyle } = useStyles();
  const isNarrow = useMediaQuery("(max-width: 768px)");
  const chartHeight = isNarrow ? 260 : 340;
  const equityOption = useMemo(
    () => buildEquityChartOption(equityCurve, colors, isNarrow),
    [colors, equityCurve, isNarrow],
  );
  const drawdownOption = useMemo(
    () => buildDrawdownChartOption(equityCurve, colors, isNarrow),
    [colors, equityCurve, isNarrow],
  );
  const holdingsOption = useMemo(
    () => buildHoldingsAllocationChartOption(equityCurve, colors, isNarrow),
    [colors, equityCurve, isNarrow],
  );
  const alphaRiskOption = useMemo(
    () => buildAlphaRiskChartOption(equityCurve, colors, isNarrow),
    [colors, equityCurve, isNarrow],
  );

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12 }}>
        <Segmented
          size="small"
          options={VIEW_OPTIONS}
          value={chartView}
          onChange={(v) => setChartView(v as string)}
          aria-label="图表视图模式"
        />
      </div>
      <div style={{ display: chartView === "all" || chartView === "nav" ? "block" : "none", marginBottom: 16 }}>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card
              title={(
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span>策略与基准净值</span>
                  <Tooltip title="对比投资组合累计净值与基准指数（如沪深300）同期相对走势">
                    <InfoCircleOutlined style={{ fontSize: 13, color: "var(--c-text-muted)" }} />
                  </Tooltip>
                </span>
              )}
              size="small"
              style={cardStyle}
              className="quant-result-card quant-chart-card"
            >
              {equityCurve.length > 0 ? (
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
          <Col xs={24} lg={8}>
            <Card
              title={(
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span>组合回撤</span>
                  <Tooltip title="投资组合净值相对历史最高峰值的动态回撤幅度与水下期间">
                    <InfoCircleOutlined style={{ fontSize: 13, color: "var(--c-text-muted)" }} />
                  </Tooltip>
                </span>
              )}
              size="small"
              style={cardStyle}
              className="quant-result-card quant-chart-card"
            >
              {equityCurve.length > 0 ? (
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
      </div>
      <div style={{ display: chartView === "all" || chartView === "holdings" || chartView === "alpha" ? "block" : "none" }}>
        <Row gutter={[16, 16]}>
          <Col
            xs={24}
            lg={chartView === "holdings" ? 24 : 12}
            style={{ display: chartView === "all" || chartView === "holdings" ? "block" : "none" }}
          >
            <Card
              title={(
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span>动态持仓演变 (资产与现金占比)</span>
                  <Tooltip title="每日收盘时投资组合在各股票与可用现金之间的配置比例（100% 堆叠）">
                    <InfoCircleOutlined style={{ fontSize: 13, color: "var(--c-text-muted)" }} />
                  </Tooltip>
                </span>
              )}
              size="small"
              style={cardStyle}
              className="quant-result-card quant-chart-card"
            >
              {equityCurve.length > 0 && equityCurve.some((p) => p.position_weights && Object.keys(p.position_weights).length > 0) ? (
                <ReactECharts
                  echarts={echarts}
                  option={holdingsOption}
                  style={{ height: chartHeight }}
                  notMerge
                  data-testid="holdings-chart"
                />
              ) : <div className="quant-chart-empty"><Empty description="暂无持仓演变数据" /></div>}
            </Card>
          </Col>
          <Col
            xs={24}
            lg={chartView === "alpha" ? 24 : 12}
            style={{ display: chartView === "all" || chartView === "alpha" ? "block" : "none" }}
          >
            <Card
              title={(
                <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                  <span>超额收益 (Alpha) 与滚动风险</span>
                  <Tooltip title="左轴为相对基准累计超额 Alpha 曲线；右轴为 60 交易日滚动年化夏普比率与滚动贝塔">
                    <InfoCircleOutlined style={{ fontSize: 13, color: "var(--c-text-muted)" }} />
                  </Tooltip>
                </span>
              )}
              size="small"
              style={cardStyle}
              className="quant-result-card quant-chart-card"
            >
              {equityCurve.length > 0 ? (
                <ReactECharts
                  echarts={echarts}
                  option={alphaRiskOption}
                  style={{ height: chartHeight }}
                  notMerge
                  data-testid="alpha-risk-chart"
                />
              ) : <div className="quant-chart-empty"><Empty description="暂无超额收益数据" /></div>}
            </Card>
          </Col>
        </Row>
      </div>
    </div>
  );
}
