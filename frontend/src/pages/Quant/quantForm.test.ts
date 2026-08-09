import dayjs from "dayjs";
import { describe, expect, it } from "vitest";
import {
  buildBacktestRequest,
  dateRangeValidationError,
  movingAverageValidationError,
  parseStockCodes,
  rsiValidationError,
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
    expect(movingAverageValidationError(20, 20)).toBe("短周期必须小于长周期");
    expect(rsiValidationError(70, 30)).toBe("买入阈值必须小于卖出阈值");
    expect(dateRangeValidationError([dayjs("2026-01-01"), dayjs("2026-01-01")])).toBe("开始日期必须早于结束日期");
    expect(dateRangeValidationError([dayjs("2020-01-01"), dayjs("2026-01-02")])).toBe("回测周期不能超过 5 年");
  });

  it("uses API presets and exposes their complete form config", () => {
    const [option] = strategyOptions([{
      key: "rsi_reversion",
      name: "定制 RSI",
      description: "定制阈值",
      config: {
        type: "rsi_reversion",
        fast_period: 5,
        slow_period: 20,
        lookback_period: 20,
        rsi_period: 9,
        buy_threshold: 25,
        sell_threshold: 75,
      },
    }]);

    expect(option.description).toBe("定制阈值");
    expect(option).toEqual(expect.objectContaining({
      scenario: "震荡行情",
      risk: "中等",
      riskColor: "gold",
      parameterSummary: "RSI 9 · 25 / 75",
    }));
    expect(strategyFormValues(option.config)).toEqual(expect.objectContaining({
      strategyType: "rsi_reversion",
      rsiPeriod: 9,
      buyThreshold: 25,
      sellThreshold: 75,
    }));
  });
});
