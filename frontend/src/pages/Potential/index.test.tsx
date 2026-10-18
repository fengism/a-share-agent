import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import PotentialPage from "./index";

vi.mock("../../api/queries", () => ({
  usePotentialDates: () => ({
    data: [
      { date: "2026-08-22", count: 2 },
      { date: "2026-08-21", count: 1 },
    ],
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  usePotentialDaily: () => ({
    data: {
      date: "2026-08-22",
      generated_at: "2026-08-22T15:30:00+08:00",
      universe_size: 300,
      evaluated: 298,
      failed_count: 2,
      market_regime: "bull",
      market_note: "沪深300近20日 +3.2%，站上MA20，站上MA60",
      market_emotion: "strong",
      advance_ratio: 0.62,
      limit_up_count: 48,
      limit_down_count: 6,
      median_change_pct: 1.2,
      hot_themes: ["低空经济", "军工"],
      items: [
        {
          code: "600487", name: "亨通光电", price: 12.34, change_pct: 3.21, market_cap: 300.5,
          turnover_pct: 4.2, amount: 102.6, industry: "通信设备",
          strategies: ["底部放量", "多头趋势"], signal_types: ["reversal", "trend"], signal_date: "2026-08-19",
          signal_age_days: 2, score: 4.6, signal_score: 3.2, quality_score: 0.8, fundamental_score: 0.5,
          theme_score: 0.6, themes: ["低空经济"], sector_strength: 1.5, risk_flags: ["RSI超买"],
          reason: "命中底部放量、多头趋势；通信设备；题材：低空经济",
        },
        {
          code: "601899", name: "紫金矿业", price: 20.1, change_pct: -0.5, market_cap: 5000,
          turnover_pct: 1.2, amount: 103.3, industry: "有色金属",
          strategies: ["多头趋势"], signal_types: ["trend"], signal_date: "2026-08-21",
          signal_age_days: 1, score: 2.0, signal_score: 2.0, quality_score: 0.0, fundamental_score: 0.0,
          theme_score: 0.0, themes: [], sector_strength: -0.5, risk_flags: [], reason: "命中多头趋势；有色金属",
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  usePotentialPerformance: () => ({
    data: {
      date: "2026-08-22",
      days: 5,
      generated_at: "2026-08-29T16:00:00",
      item_count: 2,
      evaluated_count: 2,
      win_rate: 0.5,
      average_return_pct: 3.2,
      median_return_pct: 2.0,
      average_excess_pct: 1.5,
      benchmark_return_pct: 1.7,
      message: null,
      items: [
        {
          code: "600487", name: "亨通光电", industry: "通信设备", entry_price: 12.34, exit_price: 13.5,
          return_pct: 9.4, benchmark_return_pct: 1.7, excess_return_pct: 7.7, max_return_pct: 12.0, max_drawdown_pct: -2.0,
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  usePotentialRun: () => ({ mutate: vi.fn(), isPending: false }),
  usePotentialRunStatus: () => ({
    data: { running: false, status: "idle", date: null, started_at: null, finished_at: null, error: null },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

describe("PotentialPage", () => {
  it("renders the mining summary and ranked stocks with strategy tags", () => {
    render(
      <MemoryRouter>
        <PotentialPage />
      </MemoryRouter>,
    );

    expect(screen.getByText("每日潜力股")).toBeInTheDocument();
    expect(screen.getByText(/候选池 300 只/)).toBeInTheDocument();
    expect(screen.getByText("市场多头")).toBeInTheDocument();
    expect(screen.getByText("情绪强")).toBeInTheDocument();
    expect(screen.getByText("低空经济")).toBeInTheDocument();
    expect(screen.getAllByText("亨通光电").length).toBeGreaterThan(0);
    expect(screen.getByText("底部放量")).toBeInTheDocument();
    expect(screen.getAllByText("通信设备").length).toBeGreaterThan(0);
    expect(screen.getByText("4.6")).toBeInTheDocument();
    expect(screen.getByText("历史表现复盘")).toBeInTheDocument();
    expect(screen.getByText("胜率")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
    const link = screen.getAllByRole("link", { name: /亨通光电/ })[0];
    expect(link).toHaveAttribute("href", "/stock/600487");
  });

  it("marks fresh signals with a tag", () => {
    render(
      <MemoryRouter>
        <PotentialPage />
      </MemoryRouter>,
    );

    const freshCell = screen.getByText("2026-08-19").closest("span");
    expect(freshCell).not.toBeNull();
    expect(within(freshCell!).getByText("新")).toBeInTheDocument();
  });
});
