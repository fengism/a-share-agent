import { describe, expect, it } from "vitest";
import type { PortfolioTransaction } from "../../types/portfolio";
import {
  buildPortfolioTradeMarkers,
  filterPortfolioTransactions,
  resolvePortfolioTradeDateRange,
} from "./portfolioTradeMarkers";

function transaction(
  id: number,
  side: "buy" | "sell",
  tradeTime: string,
  tradePrice = 10,
): PortfolioTransaction {
  return {
    id,
    stock_code: "600519",
    stock_name: "贵州茅台",
    side,
    trade_price: tradePrice,
    trade_time: tradeTime,
    shares: 100,
    fee: 1,
    note: "",
    created_at: tradeTime,
  };
}

describe("portfolioTradeMarkers", () => {
  it("builds B/S markers exclusively from real portfolio transactions", () => {
    const transactions = [
      transaction(1, "buy", "2026-01-02T09:31:00", 10),
      transaction(2, "buy", "2026-01-02T10:15:00", 10.2),
      transaction(3, "sell", "2026-01-05T14:50:00", 12),
      { ...transaction(4, "buy", "2026-01-06T09:30:00"), stock_code: "000001" },
    ];

    expect(buildPortfolioTradeMarkers(transactions, "600519")).toEqual([
      { date: "2026-01-02", side: "buy", label: "B×2" },
      { date: "2026-01-05", side: "sell", label: "S ¥12.00" },
    ]);
  });

  it("sorts selected stock transactions newest first without mutating input", () => {
    const transactions = [
      transaction(1, "buy", "2026-01-02T09:31:00"),
      transaction(2, "sell", "2026-01-05T14:50:00"),
    ];

    expect(filterPortfolioTransactions(transactions, "600519").map((item) => item.id)).toEqual([2, 1]);
    expect(transactions.map((item) => item.id)).toEqual([1, 2]);
  });

  it("covers the first real transaction through the requested end date", () => {
    expect(resolvePortfolioTradeDateRange(
      [
        transaction(1, "buy", "2026-01-02T09:31:00"),
        transaction(2, "sell", "2026-01-05T14:50:00"),
      ],
      "600519",
      "2026-09-19",
    )).toEqual({ startDate: "20260102", endDate: "20260919" });
  });
});
