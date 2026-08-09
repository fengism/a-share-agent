import dayjs, { type Dayjs } from "dayjs";
import type {
  QuantBacktestCreate,
  QuantStrategyConfig,
  QuantStrategyPreset,
} from "../../api/queries";

export interface QuantFormValues {
  name: string;
  source: "custom" | "portfolio";
  codes: string;
  strategyType: QuantStrategyConfig["type"];
  fastPeriod: number;
  slowPeriod: number;
  lookbackPeriod: number;
  rsiPeriod: number;
  buyThreshold: number;
  sellThreshold: number;
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
  value: QuantStrategyConfig["type"];
  label: string;
  description: string;
  scenario: string;
  risk: string;
  riskColor: string;
  parameterSummary: string;
  config: QuantStrategyConfig;
}

const STRATEGY_PRESENTATION: Record<
  QuantStrategyConfig["type"],
  Pick<StrategyOption, "scenario" | "risk" | "riskColor">
> = {
  ma_cross: { scenario: "趋势行情", risk: "中等", riskColor: "gold" },
  momentum_breakout: { scenario: "强趋势 / 突破", risk: "较高", riskColor: "volcano" },
  rsi_reversion: { scenario: "震荡行情", risk: "中等", riskColor: "gold" },
};

const DEFAULT_STRATEGY_CONFIG: QuantStrategyConfig = {
  type: "ma_cross",
  fast_period: 5,
  slow_period: 20,
  lookback_period: 20,
  rsi_period: 14,
  buy_threshold: 30,
  sell_threshold: 70,
};

export const INITIAL_VALUES: QuantFormValues = {
  name: "双均线回测",
  source: "custom",
  codes: "600519",
  strategyType: "ma_cross",
  fastPeriod: 5,
  slowPeriod: 20,
  lookbackPeriod: 20,
  rsiPeriod: 14,
  buyThreshold: 30,
  sellThreshold: 70,
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

function strategyParameterSummary(config: QuantStrategyConfig): string {
  if (config.type === "ma_cross") return `MA ${config.fast_period} / ${config.slow_period}`;
  if (config.type === "momentum_breakout") return `突破 ${config.lookback_period} 日`;
  return `RSI ${config.rsi_period} · ${config.buy_threshold} / ${config.sell_threshold}`;
}

function createStrategyOption(
  value: QuantStrategyConfig["type"],
  label: string,
  description: string,
  config: QuantStrategyConfig,
): StrategyOption {
  return {
    value,
    label,
    description,
    ...STRATEGY_PRESENTATION[config.type],
    parameterSummary: strategyParameterSummary(config),
    config,
  };
}

const FALLBACK_STRATEGIES: StrategyOption[] = [
  createStrategyOption(
    "ma_cross",
    "双均线趋势",
    "短期均线上穿长期均线后持有，跌破后退出。",
    DEFAULT_STRATEGY_CONFIG,
  ),
  createStrategyOption(
    "momentum_breakout",
    "动量突破",
    "突破近 20 日高点后跟随趋势，跌破均值后退出。",
    { ...DEFAULT_STRATEGY_CONFIG, type: "momentum_breakout" },
  ),
  createStrategyOption(
    "rsi_reversion",
    "RSI 均值回归",
    "RSI 进入超卖区间后买入，进入超买区间后退出。",
    { ...DEFAULT_STRATEGY_CONFIG, type: "rsi_reversion" },
  ),
];

export function strategyOptions(presets?: QuantStrategyPreset[]): StrategyOption[] {
  if (!presets?.length) return FALLBACK_STRATEGIES;
  return presets.map((preset) => createStrategyOption(
    preset.key,
    preset.name,
    preset.description,
    preset.config,
  ));
}

export function strategyFormValues(config: QuantStrategyConfig): Partial<QuantFormValues> {
  return {
    strategyType: config.type,
    fastPeriod: config.fast_period,
    slowPeriod: config.slow_period,
    lookbackPeriod: config.lookback_period,
    rsiPeriod: config.rsi_period,
    buyThreshold: config.buy_threshold,
    sellThreshold: config.sell_threshold,
  };
}

export function strategyConfig(values: QuantFormValues): QuantStrategyConfig {
  return {
    type: values.strategyType,
    fast_period: values.fastPeriod,
    slow_period: values.slowPeriod,
    lookback_period: values.lookbackPeriod,
    rsi_period: values.rsiPeriod,
    buy_threshold: values.buyThreshold,
    sell_threshold: values.sellThreshold,
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

export function movingAverageValidationError(fastPeriod?: number, slowPeriod?: number): string | undefined {
  if (fastPeriod == null || slowPeriod == null) return undefined;
  return fastPeriod >= slowPeriod ? "短周期必须小于长周期" : undefined;
}

export function rsiValidationError(buyThreshold?: number, sellThreshold?: number): string | undefined {
  if (buyThreshold == null || sellThreshold == null) return undefined;
  return buyThreshold >= sellThreshold ? "买入阈值必须小于卖出阈值" : undefined;
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
    },
    start_date: values.dateRange[0].format("YYYY-MM-DD"),
    end_date: values.dateRange[1].format("YYYY-MM-DD"),
    benchmark: values.benchmark.trim(),
  };
}
