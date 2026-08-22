import { useMemo } from "react";
import { Card, Col, Empty, Row } from "antd";
import ReactECharts from "echarts-for-react/lib/core";
import type { QuantBacktestResult } from "../../../api/queries";
import echarts from "../../../charts/echarts-setup";
import { useMediaQuery } from "../../../hooks/useMediaQuery";
import { useColors, useStyles } from "../../../styles/ui";
import { buildDrawdownChartOption, buildEquityChartOption } from "./backtestChartOptions";

interface BacktestChartsProps {
  equityCurve: QuantBacktestResult["equity_curve"];
}

export default function BacktestCharts({ equityCurve }: BacktestChartsProps) {
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

  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      <Col xs={24} lg={15}>
        <Card title="策略与基准净值" size="small" style={cardStyle} className="quant-result-card quant-chart-card">
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
      <Col xs={24} lg={9}>
        <Card title="组合回撤" size="small" style={cardStyle} className="quant-result-card quant-chart-card">
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
  );
}
