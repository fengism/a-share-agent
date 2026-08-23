import dayjs, { type Dayjs } from "dayjs";
import type {
  QuantBacktestCreate,
  QuantStrategyConfig,
  QuantStrategyPreset,
} from "../../api/queries";
import type { SemanticTagColor } from "../../theme/hooks";

type StrategyParameterValue = number | boolean | string;

export interface QuantFormValues {
  name: string;
  source: "custom" | "portfolio";
  codes: string;
  strategyType: string;
  strategyVersion?: string | null;
  strategyParameters: Record<string, StrategyParameterValue>;
  dateRange: [Dayjs, Dayjs];
  benchmark: string;
  initialCash: number;
  slippageBps: number;
  commissionBps: number;
  minimumCommission: number;
  stampDutyBps: number;
  transferFeeBps: number;
  lotSize: number;
  riskFreeRatePercent: number;
}

export interface StrategyOption {
  value: string;
  version: string;
  label: string;
  description: string;
  scenario: string;
  risk: string;
  riskColor: SemanticTagColor;
  riskLevel: QuantStrategyPreset["risk_level"];
  icon: string;
  parameterSummary: string;
  parameters: QuantStrategyPreset["parameters"];
  constraints: QuantStrategyPreset["constraints"];
  config: QuantStrategyConfig;
}

const RISK_PRESENTATION: Record<
  QuantStrategyPreset["risk_level"],
  Pick<StrategyOption, "risk" | "riskColor">
> = {
  low: { risk: "较低", riskColor: "success" },
  medium: { risk: "中等", riskColor: "warning" },
  high: { risk: "较高", riskColor: "up" },
};

const FALLBACK_PRESETS: QuantStrategyPreset[] = [
  {
    key: "ma_cross",
    version: "1.0.0",
    definition_hash: "builtin:ma_cross",
    name: "双均线趋势",
    description: "短期均线上穿长期均线后持有，跌破后退出。",
    scenario: "趋势行情",
    risk_level: "low",
    presentation: { icon: "line-chart" },
    parameters: [
      { key: "fast_period", type: "integer", label: "短均线", description: "短期移动平均线周期", default: 5, minimum: 2, maximum: 120 },
      { key: "slow_period", type: "integer", label: "长均线", description: "长期移动平均线周期", default: 20, minimum: 3, maximum: 250 },
    ],
    constraints: [{
      operator: "less_than",
      left: "$fast_period",
      right: "$slow_period",
      message: "短周期必须小于长周期",
    }],
    config: { type: "ma_cross", version: "1.0.0", parameters: { fast_period: 5, slow_period: 20 } },
  },
  {
    key: "momentum_breakout",
    version: "1.0.0",
    definition_hash: "builtin:momentum_breakout",
    name: "动量突破",
    description: "突破近 20 日高点后跟随趋势，跌破均值后退出。",
    scenario: "强势趋势",
    risk_level: "high",
    presentation: { icon: "rise" },
    parameters: [
      { key: "lookback_period", type: "integer", label: "突破周期", description: "计算前期高点与均值的回看周期", default: 20, minimum: 2, maximum: 250 },
    ],
    constraints: [],
    config: { type: "momentum_breakout", version: "1.0.0", parameters: { lookback_period: 20 } },
  },
  {
    key: "rsi_reversion",
    version: "1.0.0",
    definition_hash: "builtin:rsi_reversion",
    name: "RSI 均值回归",
    description: "RSI 进入超卖区间后买入，进入超买区间后退出。",
    scenario: "震荡行情",
    risk_level: "medium",
    presentation: { icon: "dashboard" },
    parameters: [
      { key: "rsi_period", type: "integer", label: "RSI 周期", description: "RSI 指标计算周期", default: 14, minimum: 2, maximum: 100 },
      { key: "buy_threshold", type: "number", label: "买入阈值", description: "RSI 低于该阈值时入场", default: 30, minimum: 0, maximum: 100 },
      { key: "sell_threshold", type: "number", label: "卖出阈值", description: "RSI 高于该阈值时退出", default: 70, minimum: 0, maximum: 100 },
    ],
    constraints: [{
      operator: "less_than",
      left: "$buy_threshold",
      right: "$sell_threshold",
      message: "买入阈值必须小于卖出阈值",
    }],
    config: {
      type: "rsi_reversion",
      version: "1.0.0",
      parameters: { rsi_period: 14, buy_threshold: 30, sell_threshold: 70 },
    },
  },
];

export const INITIAL_VALUES: QuantFormValues = {
  name: "双均线趋势 · 600519回测",
  source: "custom",
  codes: "600519",
  strategyType: "ma_cross",
  strategyVersion: "1.0.0",
  strategyParameters: { fast_period: 5, slow_period: 20 },
  dateRange: [dayjs().subtract(1, "year"), dayjs()],
  benchmark: "000300",
  initialCash: 1_000_000,
  slippageBps: 5,
  commissionBps: 3,
  minimumCommission: 5,
  stampDutyBps: 5,
  transferFeeBps: 0.1,
  lotSize: 100,
  riskFreeRatePercent: 1.5,
};

function strategyParameterSummary(preset: QuantStrategyPreset): string {
  const values = preset.config.parameters ?? {};
  return preset.parameters
    .map((parameter) => `${parameter.label} ${String(values[parameter.key] ?? parameter.default)}`)
    .join(" · ");
}

function createStrategyOption(preset: QuantStrategyPreset): StrategyOption {
  return {
    value: preset.key,
    version: preset.version,
    label: preset.name,
    description: preset.description,
    scenario: preset.scenario,
    ...RISK_PRESENTATION[preset.risk_level],
    riskLevel: preset.risk_level,
    icon: preset.presentation.icon ?? "line-chart",
    parameterSummary: strategyParameterSummary(preset),
    parameters: preset.parameters,
    constraints: preset.constraints ?? [],
    config: preset.config,
  };
}

export function strategyOptions(presets?: QuantStrategyPreset[]): StrategyOption[] {
  return (presets?.length ? presets : FALLBACK_PRESETS).map(createStrategyOption);
}

export function strategyFormValues(config: QuantStrategyConfig): Partial<QuantFormValues> {
  return {
    strategyType: config.type,
    strategyVersion: config.version,
    strategyParameters: { ...(config.parameters ?? {}) },
  };
}

export function strategyConfig(values: QuantFormValues): QuantStrategyConfig {
  return {
    type: values.strategyType,
    version: values.strategyVersion,
    parameters: { ...values.strategyParameters },
  };
}

export function parseStockCodes(value: string): string[] {
  return Array.from(new Set(value.split(/[，,\s]+/).map((code) => code.trim()).filter(Boolean)));
}

export function stockCodesValidationError(source: QuantFormValues["source"], value?: string): string | undefined {
  if (source !== "custom") return undefined;
  const codes = parseStockCodes(value ?? "");
  if (codes.length === 0) return "请输入股票代码";
  if (codes.length > 10) return "股票池最多支持 10 只股票";
  return undefined;
}

type StrategyConstraint = QuantStrategyPreset["constraints"][number];

function parameterReference(operand: StrategyConstraint["left"]): string | undefined {
  if (typeof operand !== "string" || !operand.startsWith("$")) return undefined;
  return operand.slice(1);
}

function constraintParameterKeys(constraint: StrategyConstraint): string[] {
  return [parameterReference(constraint.left), parameterReference(constraint.right)]
    .filter((key): key is string => Boolean(key));
}

function constraintOperandValue(
  operand: StrategyConstraint["left"],
  parameters: Record<string, StrategyParameterValue>,
): number | undefined {
  const reference = parameterReference(operand);
  const value = reference ? parameters[reference] : operand;
  return typeof value === "number" ? value : undefined;
}

function constraintMatches(constraint: StrategyConstraint, left: number, right: number): boolean {
  if (constraint.operator === "greater_than") return left > right;
  if (constraint.operator === "greater_or_equal") return left >= right;
  if (constraint.operator === "less_than") return left < right;
  return left <= right;
}

export function strategyConstraintDependencies(
  parameterKey: string,
  constraints: QuantStrategyPreset["constraints"],
): string[][] {
  const dependencies = constraints
    .filter((constraint) => constraintParameterKeys(constraint).includes(parameterKey))
    .flatMap(constraintParameterKeys)
    .filter((key) => key !== parameterKey);
  return Array.from(new Set(dependencies)).map((key) => ["strategyParameters", key]);
}

export function strategyConstraintValidationError(
  parameterKey: string,
  constraints: QuantStrategyPreset["constraints"],
  parameters: Record<string, StrategyParameterValue>,
): string | undefined {
  for (const constraint of constraints) {
    if (!constraintParameterKeys(constraint).includes(parameterKey)) continue;
    const left = constraintOperandValue(constraint.left, parameters);
    const right = constraintOperandValue(constraint.right, parameters);
    if (left === undefined || right === undefined) continue;
    if (!constraintMatches(constraint, left, right)) return constraint.message;
  }
  return undefined;
}

export function dateRangeValidationError(value?: [Dayjs, Dayjs]): string | undefined {
  if (!value?.[0] || !value[1]) return "请选择回测区间";
  if (!value[0].isBefore(value[1], "day")) return "开始日期必须早于结束日期";
  if (value[1].diff(value[0], "day") > 5 * 366) return "回测周期不能超过 5 年";
  return undefined;
}

export function buildBacktestRequest(values: QuantFormValues): QuantBacktestCreate {
  return {
    name: values.name.trim(),
    universe: {
      source: values.source,
      codes: values.source === "custom" ? parseStockCodes(values.codes) : [],
    },
    strategy: strategyConfig(values),
    execution: {
      initial_cash: values.initialCash,
      commission_rate: values.commissionBps / 10_000,
      minimum_commission: values.minimumCommission,
      stamp_duty_rate: values.stampDutyBps / 10_000,
      transfer_fee_rate: values.transferFeeBps / 10_000,
      slippage_bps: values.slippageBps,
      lot_size: values.lotSize,
      risk_free_rate: values.riskFreeRatePercent / 100,
      rebalance_window_days: 3,
    },
    start_date: values.dateRange[0].format("YYYY-MM-DD"),
    end_date: values.dateRange[1].format("YYYY-MM-DD"),
    benchmark: values.benchmark.trim(),
  };
}
