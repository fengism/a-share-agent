import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import TradingCalendarTab from "./TradingCalendarTab";

vi.mock("../../api/queries", () => ({
  useMarketIndexKline: () => ({
    data: {
      code: "000001",
      period: "daily",
      items: [
        { date: "2026-08-20", open: 3200, close: 3210, high: 3220, low: 3190, volume: 100, amount: 100 },
        { date: "2026-08-21", open: 3210, close: 3180, high: 3215, low: 3170, volume: 110, amount: 110 },
        { date: "2026-08-24", open: 3180, close: 3230, high: 3240, low: 3175, volume: 120, amount: 120 },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useTradingCalendar: () => ({
    data: {
      start_date: "2026-01-01",
      end_date: "2026-12-31",
      trade_dates: ["2026-08-21", "2026-08-24"],
      count: 242,
      today: "2026-08-23",
      today_is_trading_day: false,
      previous_trading_day: "2026-08-21",
      next_trading_day: "2026-08-24",
      degraded: false,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("TradingCalendarTab", () => {
  it("renders the month grid with trading-day marks and today status", () => {
    render(
      <MemoryRouter>
        <TradingCalendarTab />
      </MemoryRouter>,
    );

    expect(screen.getByText("A 股交易日历")).toBeInTheDocument();
    expect(screen.getByText(/2026 年 8 月/)).toBeInTheDocument();
    expect(screen.getByText(/2 个交易日/)).toBeInTheDocument();
    expect(screen.getByText("今天休市")).toBeInTheDocument();
    expect(screen.getByText("上一交易日 08-21")).toBeInTheDocument();
    expect(screen.getByText("下一交易日 08-24")).toBeInTheDocument();
    expect(screen.getByText(/全年 242 个/)).toBeInTheDocument();
    expect(screen.getAllByLabelText("上一月").length).toBeGreaterThan(0);
    expect(screen.getAllByLabelText("下一月").length).toBeGreaterThan(0);
  });
});
