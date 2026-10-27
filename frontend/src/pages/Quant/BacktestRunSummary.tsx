import { SettingOutlined } from "@ant-design/icons";
import { Card, Descriptions, Tag, Typography } from "antd";
import type { QuantBacktestRun } from "../../api/queries";
import { useStyles, semanticTagStyle } from "../../styles/ui";
import { formatMarketPattern } from "../../utils/marketTime";
import { QUANT_RUN_STATUS_META, quantStrategyIdentity, quantStrategyParameterSummary, quantUniverseLabel } from "./quantRun";

const { Text } = Typography;
const currencyFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });

function compactNumber(value: number): string {
  return String(Number(value.toFixed(4)));
}

export default function BacktestRunSummary({ run }: { run: QuantBacktestRun }) {
  const { cardStyle } = useStyles();
  const status = QUANT_RUN_STATUS_META[run.status];
  const strategy = run.request.strategy ?? { type: "ma_cross" };
  const execution = run.request.execution;
  const costSummary = execution?.fee_schedule === "a_share_historical"
    ? `A 股历史税率（按成交日期） · 佣金 ${compactNumber(execution.commission_rate * 10_000)} BP · 最低 ${compactNumber(execution.minimum_commission)} 元 · 滑点 ${compactNumber(execution.slippage_bps)} BP`
    : execution
    ? `佣金 ${compactNumber(execution.commission_rate * 10_000)} BP · 最低 ${compactNumber(execution.minimum_commission)} 元 · 印花税 ${compactNumber(execution.stamp_duty_rate * 10_000)} BP · 过户费 ${compactNumber(execution.transfer_fee_rate * 10_000)} BP · 滑点 ${compactNumber(execution.slippage_bps)} BP`
    : "默认执行参数";

  return (
    <Card
      title="当前回测"
      extra={<Tag style={semanticTagStyle(status.color)}>{status.label}</Tag>}
      size="small"
      style={cardStyle}
      className="quant-run-summary-card"
    >
      <div className="quant-run-summary-heading">
        <Text strong className="quant-run-summary-name">{run.name}</Text>
      </div>
      <div className="quant-run-summary-grid">
        <div className="quant-run-summary-wide"><span>本次执行策略</span><strong>{quantStrategyIdentity(strategy)}</strong></div>
        <div><span>股票池</span><strong>{quantUniverseLabel(run)}</strong></div>
        <div className="quant-run-summary-wide"><span>实际参数</span><strong>{quantStrategyParameterSummary(strategy)}</strong></div>
        <div className="quant-run-summary-wide"><span>回测区间</span><strong>{run.request.start_date} 至 {run.request.end_date}</strong></div>
        <div><span>基准</span><strong>{run.request.benchmark}</strong></div>
      </div>
      <details className="quant-run-execution-details">
        <summary><SettingOutlined />执行参数</summary>
        <Descriptions
          size="small"
          column={1}
          items={[
            { key: "created", label: "提交时间", children: formatMarketPattern(run.created_at, "YYYY-MM-DD HH:mm") },
            { key: "attempts", label: "执行次数", children: `${run.attempts} 次` },
            {
              key: "cash",
              label: "初始资金",
              children: execution ? `${currencyFormatter.format(execution.initial_cash)} 元` : "默认执行参数",
            },
            {
              key: "allocation",
              label: "资产配置",
              children: execution?.allocation_method === "risk_parity" ? "风险平价 (Risk Parity 倒数波动率)" : "等权分配 (Equal Weight)",
            },
            {
              key: "rebalance",
              label: "调仓周期",
              children: execution?.rebalance_frequency === "weekly" ? "每周首日" : execution?.rebalance_frequency === "monthly" ? "每月首日" : "每日",
            },
            {
              key: "top_n",
              label: "截面优选",
              children: execution?.top_n_selection
                ? `Top ${execution.top_n_selection} 只 (${
                    execution.ranking_metric === "momentum"
                      ? "动量优先"
                      : execution.ranking_metric === "inverse_volatility"
                      ? "低波优先"
                      : execution.ranking_metric === "turnover"
                      ? "活跃度优先"
                      : "默认原序"
                  })`
                : "全选持仓 (不筛选)",
            },
            {
              key: "slippage-model",
              label: "滑点模型",
              children: execution?.slippage_model === "square_root"
                ? `平方根市场冲击 (基础 ${compactNumber(execution.slippage_bps)} BP · 系数 ${compactNumber(execution.market_impact_coefficient ?? 10)})`
                : `固定滑点 (${compactNumber(execution?.slippage_bps ?? 5)} BP)`,
            },
            { key: "costs", label: "交易成本", children: costSummary },
            { key: "participation", label: "日成交额参与率", children: execution?.max_daily_participation_rate == null ? "不限制 / 旧版未记录" : `${compactNumber(execution.max_daily_participation_rate * 100)}%` },
            { key: "position", label: "单股仓位上限", children: `${compactNumber((execution?.max_position_weight ?? 1) * 100)}%` },
            { key: "reserve", label: "现金保留比例", children: `${compactNumber((execution?.cash_reserve_ratio ?? 0) * 100)}%` },
            ...([
              ["stop_loss_pct", "持仓止损"], ["trailing_stop_pct", "移动止损"],
              ["max_portfolio_drawdown", "回撤熔断"], ["target_annual_volatility", "目标年化波动率"],
            ] as const).map(([key, label]) => ({ key, label, children: execution?.[key] == null ? "关闭" : `${compactNumber(execution[key] * 100)}%` })),
            { key: "lot-size", label: "交易单位", children: execution ? `${execution.lot_size} 股` : "默认执行参数" },
            {
              key: "risk-free",
              label: "无风险利率",
              children: execution ? `${compactNumber(execution.risk_free_rate * 100)}%` : "默认执行参数",
            },
          ]}
        />
      </details>
    </Card>
  );
}
