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
    { label: "欧米茄比率", value: metrics.omega_ratio, suffix: "", primary: false, signed: false },
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
        {metrics.alpha != null ? (
          <Tag color={metrics.alpha >= 0 ? "success" : "default"}>
            阿尔法 α {metrics.alpha > 0 ? `+${metrics.alpha.toFixed(1)}%` : `${metrics.alpha.toFixed(1)}%`}
          </Tag>
        ) : null}
        {metrics.beta != null ? (
          <Tag color="cyan">贝塔 β {metrics.beta.toFixed(2)}</Tag>
        ) : null}
        {Math.abs(metrics.max_drawdown) >= 25 ? <Tag color="warning">历史回撤 ≥ 25%</Tag> : null}
        {metrics.win_rate != null ? <Tag>历史胜率 {metrics.win_rate.toFixed(1)}%</Tag> : null}
        {metrics.probabilistic_sharpe_ratio != null ? (
          <Tag color={metrics.probabilistic_sharpe_ratio >= 90 ? "success" : metrics.probabilistic_sharpe_ratio >= 60 ? "blue" : "default"}>
            夏普置信度 {metrics.probabilistic_sharpe_ratio.toFixed(1)}%
          </Tag>
        ) : null}
        {metrics.deflated_sharpe_ratio != null ? (
          <Tag color={metrics.deflated_sharpe_ratio >= 90 ? "success" : metrics.deflated_sharpe_ratio >= 50 ? "blue" : "orange"}>
            防过拟合检验(DSR) {metrics.deflated_sharpe_ratio.toFixed(1)}%
          </Tag>
        ) : null}
        {metrics.max_drawdown_duration_days != null && metrics.max_drawdown_duration_days > 0 ? (
          <Tag>最长水下期 {metrics.max_drawdown_duration_days} 天</Tag>
        ) : null}
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
            { key: "alpha", label: "詹森阿尔法 (α)", children: formatPercent(metrics.alpha) },
            { key: "beta", label: "系统贝塔 (β)", children: formatNumber(metrics.beta) },
            { key: "treynor", label: "特雷诺比率", children: formatNumber(metrics.treynor_ratio) },
            { key: "capture", label: "上下行捕获率", children: (metrics.upside_capture != null || metrics.downside_capture != null) ? `上行 ${formatPercent(metrics.upside_capture)} ｜ 下行 ${formatPercent(metrics.downside_capture)}` : "—" },
            { key: "omega", label: "欧米茄比率", children: formatNumber(metrics.omega_ratio) },
            { key: "dd-duration", label: "最大回撤修复期", children: metrics.max_drawdown_duration_days != null ? `${metrics.max_drawdown_duration_days} 个交易日` : "无回撤" },
            { key: "psr", label: "夏普置信度", children: metrics.probabilistic_sharpe_ratio != null ? `${metrics.probabilistic_sharpe_ratio.toFixed(1)}%` : "样本量不足" },
            { key: "dsr", label: "防过拟合(DSR)", children: metrics.deflated_sharpe_ratio != null ? `${metrics.deflated_sharpe_ratio.toFixed(1)}%` : "样本量不足" },
            { key: "allocation", label: "资产配置择时贡献", children: formatPercent(metrics.allocation_effect) },
            { key: "selection", label: "个股优选贡献", children: formatPercent(metrics.selection_effect) },
            { key: "interaction", label: "交叉交互效应", children: formatPercent(metrics.interaction_effect) },
            { key: "codes", label: "股票池", children: codes.join("、") || "-" },
            { key: "sources", label: "数据来源", children: dataSources.join("、") || "-" },
            { key: "engine", label: "引擎版本", children: engineVersion || "-" },
          ]}
        />
      </Card>

      {(metrics.allocation_effect != null || metrics.selection_effect != null) ? (
        <Card
          title="Brinson-Fachler 业绩超额归因分解"
          extra={<Tag color="geekblue">超额来源透视</Tag>}
          size="small"
          style={cardStyle}
          className="quant-result-card"
        >
          <div style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 8,
            padding: "8px 12px",
            marginBottom: 12,
            borderRadius: "var(--c-radius-sm)",
            background: "color-mix(in srgb, var(--c-primary) 6%, var(--c-nested-bg))",
            border: "1px solid color-mix(in srgb, var(--c-primary) 20%, var(--c-border))",
            fontSize: "var(--quant-font-label)",
          }}>
            <span>
              <strong>超额分解方程：</strong>
              超额收益 <span style={{ color: (metrics.excess_return ?? 0) >= 0 ? colors.up : colors.down, fontWeight: 700 }}>{formatPercent(metrics.excess_return)}</span>
              {" = "}
              择时效应 <span style={{ color: (metrics.allocation_effect ?? 0) >= 0 ? colors.up : colors.down }}>{formatPercent(metrics.allocation_effect)}</span>
              {" + "}
              选股效应 <span style={{ color: (metrics.selection_effect ?? 0) >= 0 ? colors.up : colors.down }}>{formatPercent(metrics.selection_effect)}</span>
              {" + "}
              交互效应 <span style={{ color: (metrics.interaction_effect ?? 0) >= 0 ? colors.up : colors.down }}>{formatPercent(metrics.interaction_effect)}</span>
            </span>
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
              {(metrics.allocation_effect ?? 0) > 0 ? <Tag color="blue">大盘择时正收益</Tag> : (metrics.allocation_effect ?? 0) < -1 ? <Tag color="orange">轻仓错失涨幅</Tag> : null}
              {(metrics.selection_effect ?? 0) > 0 ? <Tag color="green">选股阿尔法能力显著</Tag> : (metrics.selection_effect ?? 0) < -1 ? <Tag color="volcano">选股跑输基准</Tag> : null}
            </div>
          </div>
          <Descriptions
            size="small"
            bordered
            column={{ xs: 1, sm: 3 }}
            items={[
              {
                key: "alloc",
                label: "仓位择时/资产配置效应",
                children: (
                  <div>
                    <strong style={{ color: (metrics.allocation_effect ?? 0) >= 0 ? colors.up : colors.down }}>
                      {formatPercent(metrics.allocation_effect)}
                    </strong>
                    <div style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
                      现金与权益仓位择时贡献的超额
                    </div>
                  </div>
                ),
              },
              {
                key: "select",
                label: "个股选择效应 (Selection)",
                children: (
                  <div>
                    <strong style={{ color: (metrics.selection_effect ?? 0) >= 0 ? colors.up : colors.down }}>
                      {formatPercent(metrics.selection_effect)}
                    </strong>
                    <div style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
                      持有标的相对基准个股的超额
                    </div>
                  </div>
                ),
              },
              {
                key: "inter",
                label: "交叉交互效应 (Interaction)",
                children: (
                  <div>
                    <strong style={{ color: (metrics.interaction_effect ?? 0) >= 0 ? colors.up : colors.down }}>
                      {formatPercent(metrics.interaction_effect)}
                    </strong>
                    <div style={{ fontSize: "var(--c-font-xs)", color: "var(--c-text-muted)" }}>
                      仓位变动与标的走势联合效应
                    </div>
                  </div>
                ),
              },
            ]}
          />
        </Card>
      ) : null}

      {metrics.stress_tests && Object.keys(metrics.stress_tests).length > 0 ? (
        <Card
          title="历史极端行情压力测试 (Stress Testing)"
          extra={<Tag color="purple">历史穿透检验</Tag>}
          size="small"
          style={cardStyle}
          className="quant-result-card"
        >
          <Descriptions
            size="small"
            bordered
            column={{ xs: 1, sm: 2, lg: 3 }}
            items={Object.entries(metrics.stress_tests).map(([periodName, data]) => ({
              key: periodName,
              label: periodName,
              children: (
                <span>
                  收益：<strong style={{ color: data.return_pct >= 0 ? colors.up : colors.down }}>{formatPercent(data.return_pct)}</strong>
                  {" ｜ "}
                  回撤：<strong style={{ color: colors.down }}>{formatPercent(data.max_drawdown_pct)}</strong>
                </span>
              ),
            }))}
          />
        </Card>
      ) : null}

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
