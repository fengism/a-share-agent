import { describe, expect, it } from "vitest";
import { shouldFitChartContent } from "./chartLifecycle";

describe("shouldFitChartContent", () => {
  it("fits the first data view", () => {
    expect(shouldFitChartContent(null, "600519:daily:qfq")).toBe(true);
  });

  it("preserves the visible range for updates within the same view", () => {
    expect(shouldFitChartContent("600519:daily:qfq", "600519:daily:qfq")).toBe(false);
  });

  it("fits content when the stock, period, or indicator changes", () => {
    expect(shouldFitChartContent("600519:daily:qfq", "000001:daily:qfq")).toBe(true);
    expect(shouldFitChartContent("600519:daily:qfq", "600519:weekly:qfq")).toBe(true);
    expect(shouldFitChartContent("600519:macd", "600519:rsi")).toBe(true);
  });
});
