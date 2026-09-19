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
    { label: "总收益", value: metrics.total_return, suffix: "%", primary: true, hint: "回测区间累计收益", signed: true },
    { label: "最大回撤", value: metrics.max_drawdown, suffix: "%", primary: true, hint: "净值从峰值到谷值的跌幅", signed: true },
    { label: "夏普比率", value: metrics.sharpe_ratio, suffix: "", primary: true, hint: "单位总风险的超额回报", signed: false },
    { label: "交易日样本数", value: metrics.observation_count, suffix: "天", primary: true, hint: "结合样本量评估结果可靠性", signed: false },
    { label: "年化收益", value: metrics.annualized_return, suffix: "%", primary: false, signed: true },
    { label: "超额收益", value: metrics.excess_return, suffix: "%", primary: false, signed: true },
    { label: "索提诺比率", value: metrics.sortino_ratio, suffix: "", primary: false, signed: false },
    { label: "卡玛比率", value: metrics.calmar_ratio, suffix: "", primary: false, signed: false },
    { label: "信息比率", value: metrics.information_ratio, suffix: "", primary: false, signed: false },
  ];

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
      {[true, false].map((primary) => (
        <div className={primary ? "quant-metric-grid" : "quant-metric-grid quant-metric-grid--secondary"} role="group" aria-label={primary ? "核心回测指标" : "补充回测指标"} key={String(primary)}>
          {metricItems.filter((item) => item.primary === primary).map(({ label, value, suffix, hint, signed }) => {
            const tone = signed && value != null && value !== 0
              ? label === "最大回撤" || value < 0 ? "negative" : "positive"
              : "neutral";
            return (
              <Card size="small" style={cardStyle} className={`quant-metric-card quant-metric-card--${tone}`} key={label}>
                <Statistic
                  title={label}
                  value={value ?? (label === "交易日样本数" ? "未记录" : "—")}
                  precision={value == null ? undefined : label === "交易日样本数" ? 0 : 2}
                  suffix={value == null ? undefined : suffix}
                  styles={{ content: {
                    fontFamily: "var(--c-font-mono)",
                    fontWeight: 700,
                    color: tone === "positive" ? colors.up : tone === "negative" ? colors.down : colors.textPrimary,
                  } }}
                />
                {hint ? <div className="quant-metric-hint">{hint}</div> : null}
              </Card>
            );
          })}
        </div>
      ))}
      <div className="quant-performance-diagnostics">
        <span>本次历史表现</span>
        {metrics.benchmark_return != null && metrics.excess_return != null && metrics.excess_return > 0 ? (
          <Tag color="blue">跑赢基准 +{metrics.excess_return.toFixed(1)}%</Tag>
        ) : null}
        {Math.abs(metrics.max_drawdown) >= 25 ? <Tag color="warning">历史回撤 ≥ 25%</Tag> : null}
        {metrics.win_rate != null ? <Tag>历史胜率 {metrics.win_rate.toFixed(1)}%</Tag> : null}
        <small>仅描述该回测区间，不代表未来表现</small>
      </div>

      <Card title="回测概览" size="small" style={cardStyle} className="quant-result-card quant-result-overview">
        <Descriptions
          size="small"
          bordered
          column={{ xs: 1, sm: 2, lg: 4 }}
          items={[
            { key: "closed", label: "完整平仓次数", children: metrics.closed_trade_count ?? "旧版未记录" },
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
