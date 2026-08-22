import { Alert, Card, Descriptions, Statistic } from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
import { useColors, useStyles } from "../../../styles/ui";
import { formatNumber, formatPercent } from "./formatters";

interface BacktestMetricsProps {
  codes: QuantBacktestResult["codes"];
  dataSources: QuantBacktestResult["data_sources"];
  engineVersion: QuantBacktestResult["engine_version"];
  metrics: QuantBacktestResult["metrics"];
}

export default function BacktestMetrics({
  codes,
  dataSources,
  engineVersion,
  metrics,
}: BacktestMetricsProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const metricItems = [
    ["总收益", metrics.total_return, "%"],
    ["年化收益", metrics.annualized_return, "%"],
    ["超额收益", metrics.excess_return, "%"],
    ["最大回撤", metrics.max_drawdown, "%"],
    ["夏普比率", metrics.sharpe_ratio, ""],
    ["胜率", metrics.win_rate, "%"],
  ] as const;

  return (
    <>
      {metrics.benchmark_return == null ? (
        <Alert
          type="warning"
          showIcon
          title="该回测没有可用的基准收益"
          description="旧版结果或基准行情缺失时可能出现此情况，建议重新创建回测以获得完整的基准与超额收益。"
          style={{ marginBottom: 16 }}
        />
      ) : null}
      <div className="quant-metric-grid">
        {metricItems.map(([label, value, suffix]) => {
          const tone = label === "最大回撤"
            ? "risk"
            : typeof value === "number" && value > 0 ? "positive" : "neutral";
          return (
            <Card size="small" style={cardStyle} className={`quant-metric-card quant-metric-card--${tone}`} key={label}>
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
          );
        })}
      </div>

      <Card title="回测概览" size="small" style={cardStyle} className="quant-result-card quant-result-overview">
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
            { key: "codes", label: "股票池", children: codes.join("、") || "-" },
            { key: "sources", label: "数据来源", children: dataSources.join("、") || "-" },
            { key: "engine", label: "引擎版本", children: engineVersion || "-" },
          ]}
        />
      </Card>
    </>
  );
}
