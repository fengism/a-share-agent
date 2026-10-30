import dayjs, { type Dayjs } from "dayjs";
import type {
  QuantBacktestCreate,
  QuantStrategyConfig,
  QuantStrategyPreset,
} from "../../api/queries";
import type { SemanticTagColor } from "../../theme/hooks";
import { parseStockCode } from "../../utils/stockLinks";

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
  feeSchedule?: "custom" | "a_share_historical";
  participationPercent?: number | null;
  maxPositionPercent?: number;
  cashReservePercent?: number;
  stopLossPercent?: number | null;
  trailingStopPercent?: number | null;
  maxDrawdownPercent?: number | null;
  targetVolatilityPercent?: number | null;
  allocationMethod?: "equal" | "risk_parity";
  rebalanceFrequency?: "daily" | "weekly" | "monthly";
  slippageModel?: "fixed" | "square_root";
  marketImpactCoefficient?: number;
  topNSelection?: number | null;
  rankingMetric?: "momentum" | "inverse_volatility" | "turnover" | "equal";
  rankingLookback?: number;
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
  feeSchedule: "custom",
  participationPercent: 10,
  maxPositionPercent: 100,
  cashReservePercent: 0,
  allocationMethod: "equal",
  rebalanceFrequency: "daily",
  slippageModel: "fixed",
  marketImpactCoefficient: 10,
  topNSelection: null,
  rankingMetric: "momentum",
  rankingLookback: 20,
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

export const BUILTIN_STOCKS: Array<{ code: string; name: string }> = [
  { code: "600519", name: "贵州茅台" },
  { code: "300750", name: "宁德时代" },
  { code: "600036", name: "招商银行" },
  { code: "601318", name: "中国平安" },
  { code: "688981", name: "中芯国际" },
  { code: "600900", name: "长江电力" },
  { code: "002594", name: "比亚迪" },
  { code: "000333", name: "美的集团" },
  { code: "601899", name: "紫金矿业" },
  { code: "300308", name: "中际旭创" },
  { code: "300502", name: "新易盛" },
  { code: "601138", name: "工业富联" },
  { code: "688008", name: "澜起科技" },
  { code: "688012", name: "中微公司" },
  { code: "688256", name: "寒武纪" },
  { code: "601088", name: "中国神华" },
  { code: "601225", name: "陕西煤业" },
  { code: "600941", name: "中国移动" },
  { code: "601398", name: "工商银行" },
  { code: "601006", name: "大秦铁路" },
  { code: "600028", name: "中国石化" },
  { code: "300124", name: "汇川技术" },
  { code: "300274", name: "阳光电源" },
  { code: "600031", name: "三一重工" },
  { code: "600660", name: "福耀玻璃" },
  { code: "600276", name: "恒瑞医药" },
  { code: "603259", name: "药明康德" },
  { code: "688235", name: "百济神州" },
  { code: "300760", name: "迈瑞医疗" },
  { code: "600436", name: "片仔癀" },
  { code: "000001", name: "平安银行" },
  { code: "000002", name: "万科A" },
  { code: "000858", name: "五粮液" },
  { code: "600000", name: "浦发银行" },
  { code: "600585", name: "海螺水泥" },
  { code: "601888", name: "中国中免" },
  { code: "603288", name: "海天味业" },
  { code: "002475", name: "立讯精密" },
  { code: "002415", name: "海康威视" },
  { code: "300059", name: "东方财富" },
  { code: "00700", name: "腾讯控股" },
  { code: "09988", name: "阿里巴巴" },
  { code: "03690", name: "美团" },
];

const dynamicStockMap = new Map<string, string>();
const dynamicNameToCodeMap = new Map<string, string>();

for (const item of BUILTIN_STOCKS) {
  dynamicStockMap.set(item.code, item.name);
  dynamicNameToCodeMap.set(item.name, item.code);
}

export function registerStockInfo(code: string, name: string): void {
  const cleanCode = code.trim();
  const cleanName = name.trim();
  if (!cleanCode || !cleanName) return;
  dynamicStockMap.set(cleanCode, cleanName);
  dynamicNameToCodeMap.set(cleanName, cleanCode);
}

export function getStockName(code: string): string | undefined {
  return dynamicStockMap.get(code.trim());
}

export function resolveStockNameOrCode(token: string): string | undefined {
  const raw = token.trim();
  if (!raw) return undefined;
  if (/^\d{5,6}$/.test(raw)) return raw;
  const parsed = parseStockCode(raw);
  if (parsed && (parsed.market === "cn" || /^\d{5,6}$/.test(parsed.code))) {
    return parsed.code;
  }
  const byExact = dynamicNameToCodeMap.get(raw) || dynamicNameToCodeMap.get(raw.replace(/\s+/g, ""));
  if (byExact) return byExact;
  for (const [name, code] of dynamicNameToCodeMap.entries()) {
    if (name.includes(raw) || raw.includes(name)) {
      return code;
    }
  }
  return undefined;
}

export function splitInputSearch(value: string = ""): { prefix: string; searchTerm: string } {
  const match = value.match(/^(.*[,\s，]+)([^,\s，]*)$/);
  if (match) {
    return { prefix: match[1], searchTerm: match[2].trim() };
  }
  return { prefix: "", searchTerm: value.trim() };
}

export function parseStockCodes(value: string): string[] {
  return Array.from(new Set(
    value
      .split(/[，,\s]+/)
      .map((code) => code.trim())
      .filter(Boolean)
      .map((token) => resolveStockNameOrCode(token) ?? token)
  ));
}

export function computeBacktestName(
  strategyLabel: string,
  source: QuantFormValues["source"],
  codesValue: string,
): string {
  if (source === "portfolio") {
    return `${strategyLabel} · 当前持仓回测`;
  }
  const codes = parseStockCodes(codesValue);
  if (codes.length === 0) {
    return `${strategyLabel}回测`;
  }
  if (codes.length === 1) {
    return `${strategyLabel} · ${codes[0]}回测`;
  }
  return `${strategyLabel} · ${codes.length}只股票回测`;
}

export function isAutoGeneratedBacktestName(
  currentName: string | undefined,
  strategyOptionsList: StrategyOption[],
): boolean {
  if (!currentName || !currentName.trim()) return true;
  const trimmed = currentName.trim();
  if (trimmed === INITIAL_VALUES.name || trimmed === "双均线回测") return true;
  if (/^\d+ 只股票组合回测$/.test(trimmed)) return true;
  return strategyOptionsList.some((opt) => (
    trimmed === `${opt.label}回测` ||
    (trimmed.startsWith(`${opt.label} · `) && trimmed.endsWith("回测"))
  ));
}

export function stockCodesValidationError(source: QuantFormValues["source"], value?: string): string | undefined {
  if (source !== "custom") return undefined;
  const codes = parseStockCodes(value ?? "");
  if (codes.length === 0) return "请输入股票代码";
  if (codes.length > 30) return "股票池最多支持 30 只股票";
  const invalid = codes.filter((c) => !/^\d{5,6}$/.test(c));
  if (invalid.length > 0) {
    return `股票代码或名称“${invalid[0]}”无法识别，请输入有效代码或搜索股票`;
  }
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
      slippage_model: values.slippageModel ?? "fixed",
      market_impact_coefficient: values.marketImpactCoefficient ?? 10,
      allocation_method: values.allocationMethod ?? "equal",
      rebalance_frequency: values.rebalanceFrequency ?? "daily",
      top_n_selection: values.topNSelection == null ? null : values.topNSelection,
      ranking_metric: values.rankingMetric ?? "momentum",
      ranking_lookback: values.rankingLookback ?? 20,
      lot_size: values.lotSize,
      risk_free_rate: values.riskFreeRatePercent / 100,
      rebalance_window_days: 3,
      fee_schedule: values.feeSchedule ?? "custom",
      max_daily_participation_rate: values.participationPercent === null ? null : (values.participationPercent ?? 10) / 100,
      max_position_weight: (values.maxPositionPercent ?? 100) / 100,
      cash_reserve_ratio: (values.cashReservePercent ?? 0) / 100,
      stop_loss_pct: values.stopLossPercent == null ? null : values.stopLossPercent / 100,
      trailing_stop_pct: values.trailingStopPercent == null ? null : values.trailingStopPercent / 100,
      max_portfolio_drawdown: values.maxDrawdownPercent == null ? null : values.maxDrawdownPercent / 100,
      target_annual_volatility: values.targetVolatilityPercent == null ? null : values.targetVolatilityPercent / 100,
    },
    start_date: values.dateRange[0].format("YYYY-MM-DD"),
    end_date: values.dateRange[1].format("YYYY-MM-DD"),
    benchmark: values.benchmark.trim(),
  };
}
