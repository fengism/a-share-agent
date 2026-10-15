import { describe, expect, it } from "vitest";
import { calculateKDJ, calculateMACD, calculateRSI } from "./technicalIndicators";

describe("technicalIndicators", () => {
  const sampleBars = [
    { date: "2026-01-01", open: 10, high: 12, low: 9, close: 11 },
    { date: "2026-01-02", open: 11, high: 13, low: 10, close: 12 },
    { date: "2026-01-03", open: 12, high: 14, low: 11, close: 13 },
    { date: "2026-01-04", open: 13, high: 13.5, low: 11.5, close: 12 },
    { date: "2026-01-05", open: 12, high: 12.5, low: 10.5, close: 11 },
    { date: "2026-01-06", open: 11, high: 12, low: 10, close: 11.5 },
    { date: "2026-01-07", open: 11.5, high: 13, low: 11, close: 12.5 },
    { date: "2026-01-08", open: 12.5, high: 14, low: 12, close: 13.5 },
    { date: "2026-01-09", open: 13.5, high: 15, low: 13, close: 14.5 },
    { date: "2026-01-10", open: 14.5, high: 15.5, low: 14, close: 15 },
  ];

  it("calculates MACD correctly with dif, dea and macd bar", () => {
    const result = calculateMACD(sampleBars);
    expect(result.dif).toHaveLength(sampleBars.length);
    expect(result.dea).toHaveLength(sampleBars.length);
    expect(result.macd).toHaveLength(sampleBars.length);

    expect(result.dif[0].value).toBe(0);
    expect(result.dea[0].value).toBe(0);
    expect(result.macd[0].value).toBe(0);

    // MACD increases when price keeps rising
    const last = result.macd[result.macd.length - 1];
    expect(last.value).toBeGreaterThan(0);
    expect(result.dif[result.dif.length - 1].value).toBeGreaterThan(result.dea[result.dea.length - 1].value);
  });

  it("calculates KDJ correctly within standard bounds", () => {
    const result = calculateKDJ(sampleBars);
    expect(result.k).toHaveLength(sampleBars.length);
    expect(result.d).toHaveLength(sampleBars.length);
    expect(result.j).toHaveLength(sampleBars.length);

    // Initial K & D should evolve from 50
    expect(result.k[0].value).toBeGreaterThanOrEqual(0);
    expect(result.k[0].value).toBeLessThanOrEqual(100);

    // On continuous rise, K and J should rise above 50
    const lastIdx = sampleBars.length - 1;
    expect(result.k[lastIdx].value).toBeGreaterThan(50);
    expect(result.j[lastIdx].value).toBeGreaterThan(result.k[lastIdx].value);
  });

  it("calculates RSI correctly for 6, 12, 24 periods", () => {
    const result = calculateRSI(sampleBars);
    expect(result.rsi6).toHaveLength(sampleBars.length);
    expect(result.rsi12).toHaveLength(sampleBars.length);
    expect(result.rsi24).toHaveLength(sampleBars.length);

    for (const pt of result.rsi6) {
      expect(pt.value).toBeGreaterThanOrEqual(0);
      expect(pt.value).toBeLessThanOrEqual(100);
    }
  });

  it("handles empty data gracefully", () => {
    expect(calculateMACD([])).toEqual({ dif: [], dea: [], macd: [] });
    expect(calculateKDJ([])).toEqual({ k: [], d: [], j: [] });
    expect(calculateRSI([])).toEqual({ rsi6: [], rsi12: [], rsi24: [] });
  });
});
