import dayjs from "dayjs";
import { describe, expect, it } from "vitest";
import {
  buildBacktestRequest,
  dateRangeValidationError,
  parseStockCodes,
  strategyConstraintDependencies,
  strategyConstraintValidationError,
  stockCodesValidationError,
  strategyFormValues,
  strategyOptions,
  INITIAL_VALUES,
} from "./quantForm";

describe("quant form helpers", () => {
  it("normalizes and deduplicates custom stock codes", () => {
    expect(parseStockCodes("600519， 000001 600519")).toEqual(["600519", "000001"]);
    expect(buildBacktestRequest({ ...INITIAL_VALUES, codes: "600519, 600519" }).universe.codes).toEqual(["600519"]);
  });

  it("converts user-facing BP and percentage units into API rates", () => {
    const execution = buildBacktestRequest({
      ...INITIAL_VALUES,
      commissionBps: 4.5,
      minimumCommission: 3,
      stampDutyBps: 6,
      transferFeeBps: 0.2,
      lotSize: 200,
      riskFreeRatePercent: 2.5,
    }).execution;

    expect(execution).toEqual(expect.objectContaining({
      commission_rate: 0.00045,
      minimum_commission: 3,
      stamp_duty_rate: 0.0006,
      transfer_fee_rate: 0.00002,
      slippage_bps: 5,
      lot_size: 200,
      risk_free_rate: 0.025,
    }));
  });

  it("mirrors backend validation boundaries", () => {
    const elevenCodes = Array.from({ length: 11 }, (_, index) => String(600000 + index)).join(",");
    expect(stockCodesValidationError("custom", " ")).toBe("请输入股票代码");
    expect(stockCodesValidationError("custom", elevenCodes)).toBe("股票池最多支持 10 只股票");
    expect(stockCodesValidationError("portfolio", "")).toBeUndefined();
    expect(dateRangeValidationError([dayjs("2026-01-01"), dayjs("2026-01-01")])).toBe("开始日期必须早于结束日期");
    expect(dateRangeValidationError([dayjs("2020-01-01"), dayjs("2026-01-02")])).toBe("回测周期不能超过 5 年");
  });

  it("uses API presets and exposes their complete form config", () => {
    const [option] = strategyOptions([{
      key: "rsi_reversion",
      version: "2.0.0",
      definition_hash: "sha256:custom",
      name: "定制 RSI",
      description: "定制阈值",
      scenario: "定制震荡",
      risk_level: "low",
      presentation: { icon: "dashboard" },
      constraints: [{
        operator: "less_than",
        left: "$buy_threshold",
        right: "$sell_threshold",
        message: "买入阈值必须小于卖出阈值",
      }],
      parameters: [
        { key: "rsi_period", type: "integer", label: "RSI 周期", description: "", default: 9, minimum: 2, maximum: 100 },
        { key: "buy_threshold", type: "number", label: "买入阈值", description: "", default: 25, minimum: 0, maximum: 100 },
        { key: "sell_threshold", type: "number", label: "卖出阈值", description: "", default: 75, minimum: 0, maximum: 100 },
      ],
      config: {
        type: "rsi_reversion",
        version: "2.0.0",
        parameters: { rsi_period: 9, buy_threshold: 25, sell_threshold: 75 },
      },
    }]);

    expect(option.description).toBe("定制阈值");
    expect(option).toEqual(expect.objectContaining({
      scenario: "定制震荡",
      risk: "较低",
      riskColor: "success",
      parameterSummary: "RSI 周期 9 · 买入阈值 25 · 卖出阈值 75",
    }));
    expect(strategyFormValues(option.config)).toEqual(expect.objectContaining({
      strategyType: "rsi_reversion",
      strategyVersion: "2.0.0",
      strategyParameters: { rsi_period: 9, buy_threshold: 25, sell_threshold: 75 },
    }));
  });

  it("evaluates descriptor constraints without strategy-specific branches", () => {
    const constraints = [
      {
        operator: "less_than" as const,
        left: "$fast_period",
        right: "$slow_period",
        message: "短周期必须小于长周期",
      },
      {
        operator: "greater_or_equal" as const,
        left: "$slow_period",
        right: 10,
        message: "长周期不能小于 10",
      },
    ];

    expect(strategyConstraintDependencies("fast_period", constraints)).toEqual([
      ["strategyParameters", "slow_period"],
    ]);
    expect(strategyConstraintValidationError(
      "fast_period",
      constraints,
      { fast_period: 20, slow_period: 10 },
    )).toBe("短周期必须小于长周期");
    expect(strategyConstraintValidationError(
      "slow_period",
      constraints,
      { fast_period: 5, slow_period: 8 },
    )).toBe("长周期不能小于 10");
    expect(strategyConstraintValidationError(
      "slow_period",
      constraints,
      { fast_period: 5, slow_period: 20 },
    )).toBeUndefined();
  });
});
