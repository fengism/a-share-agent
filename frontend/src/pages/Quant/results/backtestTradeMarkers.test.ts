import { describe, expect, it } from "vitest";
import { buildBacktestTradeMarkers, resolveBacktestDateRange, resolveBacktestTradeCodes } from "./backtestTradeMarkers";

const trades = [
  { date: "2026-01-03", code: "600519", side: "buy" as const, price: 10, shares: 100, amount: 1000, fee: 1, realized_pnl: null },
  { date: "2026-01-03", code: "600519", side: "buy" as const, price: 11, shares: 100, amount: 1100, fee: 1, realized_pnl: null },
  { date: "2026-01-05", code: "600519", side: "sell" as const, price: 12, shares: 200, amount: 2400, fee: 1, realized_pnl: 300 },
  { date: "2026-01-04", code: "000001", side: "buy" as const, price: 8, shares: 100, amount: 800, fee: 1, realized_pnl: null },
];

describe("backtestTradeMarkers", () => {
  it("groups same-day same-side trades for the selected stock", () => {
    expect(buildBacktestTradeMarkers(trades, "600519")).toEqual([
      { date: "2026-01-03", side: "buy", label: "买×2" },
      { date: "2026-01-05", side: "sell", label: "卖" },
    ]);
  });

  it("keeps requested stock order and appends traded codes outside the request", () => {
    expect(resolveBacktestTradeCodes(["600519", "000001", "300750"], trades)).toEqual([
      "600519", "000001",
    ]);
  });

  it("resolves the full chart range from equity and trade dates", () => {
    expect(resolveBacktestDateRange(
      [{ date: "2026-01-02", equity: 1, benchmark: 1, drawdown: 0 }],
      trades,
    )).toEqual({ startDate: "20260102", endDate: "20260105" });
  });
});
