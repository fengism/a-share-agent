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
      items: [
        {
          code: "600487", name: "亨通光电", price: 12.34, change_pct: 3.21, market_cap: 300.5,
          turnover_pct: 4.2, amount: 102.6, strategies: ["底部放量", "多头趋势"], signal_date: "2026-08-19",
          signal_age_days: 2, score: 4.0,
        },
        {
          code: "601899", name: "紫金矿业", price: 20.1, change_pct: -0.5, market_cap: 5000,
          turnover_pct: 1.2, amount: 103.3, strategies: ["多头趋势"], signal_date: "2026-08-21",
          signal_age_days: 1, score: 2.0,
        },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  usePotentialRun: () => ({ mutate: vi.fn(), isPending: false }),
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
    expect(screen.getByText("亨通光电")).toBeInTheDocument();
    expect(screen.getByText("底部放量")).toBeInTheDocument();
    expect(screen.getByText("4.0")).toBeInTheDocument();
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
