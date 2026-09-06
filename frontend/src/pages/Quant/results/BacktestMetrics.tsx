import { Alert, Card, Descriptions, Statistic, Tag } from "antd";
import type { QuantBacktestResult } from "../../../api/queries";
import { useColors, useStyles } from "../../../styles/ui";
import { formatNumber, formatPercent } from "./formatters";

interface BacktestMetricsProps {
  codes: QuantBacktestResult["codes"];
  dataSources: QuantBacktestResult["data_sources"];
  engineVersion: QuantBacktestResult["engine_version"];
  metrics: QuantBacktestResult["metrics"];
  holdoutValidation: QuantBacktestResult["holdout_validation"];
}

export default function BacktestMetrics({
  codes,
  dataSources,
  engineVersion,
  metrics,
  holdoutValidation,
}: BacktestMetricsProps) {
  const colors = useColors();
  const { cardStyle } = useStyles();
  const metricItems = [
    ["总收益", metrics.total_return, "%"],
    ["年化收益", metrics.annualized_return, "%"],
    ["超额收益", metrics.excess_return, "%"],
    ["最大回撤", metrics.max_drawdown, "%"],
    ["夏普比率", metrics.sharpe_ratio, ""],
    ["索提诺比率", metrics.sortino_ratio, ""],
    ["卡玛比率", metrics.calmar_ratio, ""],
    ["信息比率", metrics.information_ratio, ""],
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
      {/* Strategy performance diagnostic tags */}
      <div className="quant-performance-diagnostics" style={{ display: "flex", gap: "8px", flexWrap: "wrap", marginBottom: "12px", alignItems: "center" }}>
        <span style={{ fontSize: "var(--c-font-xs)", fontWeight: "var(--c-weight-bold)", color: colors.textSecondary }}>策略体检:</span>
        {metrics.total_return > (metrics.benchmark_return ?? 0) ? (
          <Tag color="success">⭐ 跑赢基准 (Alpha {(metrics.excess_return ?? 0) > 0 ? `+${metrics.excess_return?.toFixed(1)}` : metrics.excess_return?.toFixed(1)}%)</Tag>
        ) : null}
        {metrics.sharpe_ratio != null && metrics.sharpe_ratio >= 1.0 ? (
          <Tag color="blue">⚡ 风险调整收益优良 (Sharpe {metrics.sharpe_ratio.toFixed(2)})</Tag>
        ) : null}
        {Math.abs(metrics.max_drawdown) <= 10 ? (
          <Tag color="cyan">🛡️ 回撤控制优良 (&lt;10%)</Tag>
        ) : Math.abs(metrics.max_drawdown) >= 25 ? (
          <Tag color="warning">⚠️ 历史回撤偏大 (&gt;25%)</Tag>
        ) : null}
        {metrics.win_rate != null && metrics.win_rate >= 55 ? (
          <Tag color="purple">🎯 胜率显著 ({metrics.win_rate.toFixed(1)}%)</Tag>
        ) : null}
      </div>
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
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    letterSpacing: "-0.01em",
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
            { key: "downside-volatility", label: "下行波动", children: formatPercent(metrics.downside_volatility) },
            { key: "tracking-error", label: "跟踪误差", children: formatPercent(metrics.tracking_error) },
            { key: "win-rate", label: "胜率", children: formatPercent(metrics.win_rate) },
            { key: "turnover", label: "换手率", children: formatPercent(metrics.turnover_rate) },
            { key: "trades", label: "交易次数", children: `${metrics.trade_count} 次` },
            { key: "profit-loss", label: "盈亏比", children: formatNumber(metrics.profit_loss_ratio) },
            { key: "codes", label: "股票池", children: codes.join("、") || "-" },
            { key: "sources", label: "数据来源", children: dataSources.join("、") || "-" },
            { key: "engine", label: "引擎版本", children: engineVersion || "-" },
          ]}
        />
      </Card>

      {holdoutValidation ? (
        <Card
          title="后段样本验证"
          extra={<Tag color="blue">独立资金</Tag>}
          size="small"
          style={cardStyle}
          className="quant-result-card quant-holdout-card"
        >
          <Descriptions
            size="small"
            bordered
            column={{ xs: 1, sm: 2, lg: 4 }}
            items={[
              {
                key: "period",
                label: "验证区间",
                children: `${holdoutValidation.start_date} 至 ${holdoutValidation.end_date}`,
              },
              {
                key: "training-ratio",
                label: "前段样本占比",
                children: formatPercent(holdoutValidation.training_ratio * 100),
              },
              {
                key: "observations",
                label: "观测数",
                children: `${holdoutValidation.observation_count} 个`,
              },
              {
                key: "return",
                label: "总收益",
                children: formatPercent(holdoutValidation.metrics.total_return),
              },
              {
                key: "drawdown",
                label: "最大回撤",
                children: formatPercent(holdoutValidation.metrics.max_drawdown),
              },
              {
                key: "sharpe",
                label: "夏普比率",
                children: formatNumber(holdoutValidation.metrics.sharpe_ratio),
              },
              {
                key: "sortino",
                label: "索提诺比率",
                children: formatNumber(holdoutValidation.metrics.sortino_ratio),
              },
              {
                key: "trades",
                label: "交易次数",
                children: `${holdoutValidation.metrics.trade_count} 次`,
              },
            ]}
          />
        </Card>
      ) : null}
    </>
  );
}
