import type { ReactNode } from "react";
import { SafetyOutlined, SlidersOutlined, WalletOutlined } from "@ant-design/icons";
import { Form, InputNumber, Select } from "antd";
import type { QuantFormValues } from "./quantForm";

function ExecutionGroup({ id, title, description, icon, children }: {
  id: string;
  title: string;
  description: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <section className="quant-execution-group" aria-labelledby={id}>
      <div className="quant-execution-group__heading">
        <span aria-hidden="true">{icon}</span>
        <div><h3 id={id}>{title}</h3><p>{description}</p></div>
      </div>
      <div className="quant-execution-group__fields">{children}</div>
    </section>
  );
}

export default function BacktestAdvancedFields() {
  const form = Form.useFormInstance<QuantFormValues>();
  const historicalFees = Form.useWatch("feeSchedule", form) === "a_share_historical";
  const isSquareRootSlippage = Form.useWatch("slippageModel", form) === "square_root";

  return (
    <div className="quant-advanced-execution-fields">
      <ExecutionGroup id="quant-cost-title" title="交易成本" description="税费与收益计算假设" icon={<WalletOutlined />}>
        <Form.Item
          className="quant-execution-field-wide"
          name="feeSchedule"
          label="税费模式"
          tooltip="历史模式适用于 2015-08-01 起的 A 股，按成交日期计算印花税和过户费，覆盖固定税率；佣金仍自定义。"
          extra={historicalFees ? "历史税率已接管印花税、过户费" : "1 BP = 0.01%"}
        >
          <Select options={[{ value: "custom", label: "自定义固定税率" }, { value: "a_share_historical", label: "A 股历史税率" }]} />
        </Form.Item>
        <Form.Item
          className="quant-execution-field-wide"
          name="slippageModel"
          label="滑点模型"
          tooltip="固定滑点为基准固定损耗；平方根市场冲击模型遵循经典 Almgren-Chriss 定律，依据订单金额占当日成交额比例动态增加冲击成本。"
        >
          <Select
            options={[
              { value: "fixed", label: "固定滑点 (Fixed)" },
              { value: "square_root", label: "平方根市场冲击 (Square-Root Impact)" },
            ]}
          />
        </Form.Item>
        {isSquareRootSlippage && (
          <Form.Item
            name="marketImpactCoefficient"
            label="市场冲击系数（BP）"
            tooltip="平方根冲击强度系数，通常介于 5-50 BP 之间。"
            rules={[{ required: true, type: "number", min: 0, max: 500, message: "冲击系数需在 0-500 之间" }]}
          >
            <InputNumber min={0} max={500} step={1} />
          </Form.Item>
        )}
        {([
          ["commissionBps", "佣金（BP）", 100, 0.1, false],
          ["minimumCommission", "最低佣金（元）", 1000, 1, false],
          ["stampDutyBps", "印花税（BP）", 100, 0.1, historicalFees],
          ["transferFeeBps", "过户费（BP）", 100, 0.01, historicalFees],
        ] as const).map(([name, label, max, step, disabled]) => (
          <Form.Item key={name} name={name} label={label} rules={[{ required: true, type: "number", min: 0, max, message: `${label}需在 0-${max} 之间` }]}>
            <InputNumber min={0} max={max} step={step} disabled={disabled} />
          </Form.Item>
        ))}
        <Form.Item name="riskFreeRatePercent" label="无风险利率（%）" rules={[{ required: true, type: "number", min: -10, max: 50, message: "无风险利率需在 -10%-50%" }]}>
          <InputNumber min={-10} max={50} step={0.1} />
        </Form.Item>
      </ExecutionGroup>
      <ExecutionGroup id="quant-position-title" title="仓位管理" description="控制成交规模与资金使用" icon={<SlidersOutlined />}>
        <Form.Item
          className="quant-execution-field-wide"
          name="allocationMethod"
          label="标的资金分配"
          tooltip="等权分配：活跃标的平均分配资金；风险平价：依据近 20 个交易日波动率倒数加权，低波动品种赋予更高权重以均衡风险。"
        >
          <Select
            options={[
              { value: "equal", label: "等权分配 (Equal Weight)" },
              { value: "risk_parity", label: "风险平价 (Risk Parity 倒数波动率)" },
            ]}
          />
        </Form.Item>
        <Form.Item
          className="quant-execution-field-wide"
          name="rebalanceFrequency"
          label="组合调仓周期"
          tooltip="每日：每个交易日响应信号；每周/每月：仅在自然周/月的首个交易日调仓，有效过滤假突破并大幅降低交易摩擦（止损保护仍每日生效）。"
        >
          <Select
            options={[
              { value: "daily", label: "每日调仓 (Daily)" },
              { value: "weekly", label: "每周首日调仓 (Weekly)" },
              { value: "monthly", label: "每月首日调仓 (Monthly)" },
            ]}
          />
        </Form.Item>
        <Form.Item
          name="topNSelection"
          label="截面优选（Top N 只）"
          tooltip="多标的资金分散控制：当股票池内有多只标的触发买入时，按排序因子优选得分最高的前 N 只持有，其余空仓。留空则全部持有。"
          rules={[{ type: "number", min: 1, max: 30 }]}
        >
          <InputNumber min={1} max={30} placeholder="留空不限制" />
        </Form.Item>
        <Form.Item
          className="quant-execution-field-wide"
          name="rankingMetric"
          label="截面选股因子"
          tooltip="多标的截面优选评分指标：动量优先选择近期涨幅最大股票；波动率优先选择走势最稳健股票；换手率优先选择资金参与度最活跃股票。"
        >
          <Select
            options={[
              { value: "momentum", label: "动量优先 (Momentum 近期收益最高)" },
              { value: "inverse_volatility", label: "低波优先 (Low Volatility 走势最稳)" },
              { value: "turnover", label: "活跃优先 (Liquidity 成交最活跃)" },
              { value: "equal", label: "默认顺序 (Equal 股票池原序)" },
            ]}
          />
        </Form.Item>
        {([
          ["participationPercent", "日成交额参与率（%）", 0.01, 100, "留空不限制；默认 10%，成交额缺失时不成交。", "留空不限"],
          ["maxPositionPercent", "单股仓位上限（%）", 0.01, 100, "默认 100%；以开盘估值计算，无法成交时可能超限。", "默认 100%"],
          ["cashReservePercent", "现金保留比例（%）", 0, 99.99, "默认 0%；买入时扣除预留现金。", "默认 0%"],
          ["targetVolatilityPercent", "目标年化波动率（%）", 0.01, 200, "留空关闭；只降仓不加杠杆，需 20 个对齐的历史收益样本。", "留空关闭"],
        ] as const).map(([name, label, min, max, tooltip, placeholder]) => (
          <Form.Item key={name} name={name} label={label} tooltip={tooltip} rules={[{ type: "number", min, max }]}>
            <InputNumber min={min} max={max} placeholder={placeholder} />
          </Form.Item>
        ))}
        <Form.Item name="lotSize" label="交易单位（股）" rules={[{ required: true, type: "number", min: 1, max: 10_000, message: "交易单位需在 1-10000 股" }]}>
          <InputNumber min={1} max={10_000} step={100} precision={0} />
        </Form.Item>
        <p className="quant-execution-group__note">按日线模拟成交，无法成交时仓位约束可能暂时超限。</p>
      </ExecutionGroup>
      <ExecutionGroup id="quant-exit-title" title="退出保护" description="可选配置 · 留空即关闭" icon={<SafetyOutlined />}>
        {([
          ["stopLossPercent", "持仓止损（%）", "按含费用的实际持仓成本计算。"],
          ["trailingStopPercent", "移动止损（%）", "按持仓后的最高价计算。"],
          ["maxDrawdownPercent", "组合回撤熔断（%）", "收盘触发，之后尝试清仓且不再开仓。"],
        ] as const).map(([name, label, tooltip]) => (
          <Form.Item key={name} name={name} label={label} tooltip={tooltip} rules={[{ type: "number", min: 0.01, max: 99.99 }]}>
            <InputNumber min={0.01} max={99.99} placeholder="留空关闭" />
          </Form.Item>
        ))}
        <p className="quant-execution-group__note">止损信号不保证成交；停牌、跌停和流动性不足可能延迟退出。</p>
      </ExecutionGroup>
    </div>
  );
}
