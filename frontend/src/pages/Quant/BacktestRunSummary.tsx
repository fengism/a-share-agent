import { Card, Descriptions, Tag, Typography } from "antd";
import dayjs from "dayjs";
import type { QuantBacktestRun } from "../../api/queries";
import { useStyles } from "../../styles/ui";
import { QUANT_RUN_STATUS_META, QUANT_STRATEGY_LABELS, quantUniverseLabel } from "./quantRun";

const { Text } = Typography;
const currencyFormatter = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });

function compactNumber(value: number): string {
  return String(Number(value.toFixed(4)));
}

export default function BacktestRunSummary({ run }: { run: QuantBacktestRun }) {
  const { cardStyle } = useStyles();
  const status = QUANT_RUN_STATUS_META[run.status];
  const strategyType = run.request.strategy?.type ?? "ma_cross";
  const execution = run.request.execution;
  const costSummary = execution
    ? `佣金 ${compactNumber(execution.commission_rate * 10_000)} BP · 最低 ${compactNumber(execution.minimum_commission)} 元 · 印花税 ${compactNumber(execution.stamp_duty_rate * 10_000)} BP · 过户费 ${compactNumber(execution.transfer_fee_rate * 10_000)} BP · 滑点 ${compactNumber(execution.slippage_bps)} BP`
    : "默认执行参数";

  return (
    <Card title="当前回测" size="small" style={cardStyle} className="quant-run-summary-card">
      <div className="quant-run-summary-heading">
        <Text strong className="quant-run-summary-name">{run.name}</Text>
        <Tag color={status.color}>{status.label}</Tag>
      </div>
      <Descriptions
        size="small"
        column={{ xs: 1, sm: 2, lg: 3 }}
        items={[
          { key: "strategy", label: "策略", children: QUANT_STRATEGY_LABELS[strategyType] },
          { key: "universe", label: "股票池", children: quantUniverseLabel(run) },
          { key: "period", label: "回测区间", children: `${run.request.start_date} 至 ${run.request.end_date}` },
          { key: "benchmark", label: "基准", children: run.request.benchmark },
          { key: "created", label: "提交时间", children: dayjs.unix(run.created_at).format("YYYY-MM-DD HH:mm") },
          { key: "attempts", label: "执行次数", children: `${run.attempts} 次` },
          {
            key: "cash",
            label: "初始资金",
            children: execution ? `${currencyFormatter.format(execution.initial_cash)} 元` : "默认执行参数",
          },
          { key: "costs", label: "交易成本", children: costSummary },
          { key: "lot-size", label: "交易单位", children: execution ? `${execution.lot_size} 股` : "默认执行参数" },
          {
            key: "risk-free",
            label: "无风险利率",
            children: execution ? `${compactNumber(execution.risk_free_rate * 100)}%` : "默认执行参数",
          },
        ]}
      />
    </Card>
  );
}
