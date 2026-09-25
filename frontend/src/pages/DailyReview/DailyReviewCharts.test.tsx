import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { DailyReviewDataSnapshot } from "../../types/dailyReview";
import DailyReviewCharts from "./DailyReviewCharts";

function createSnapshot(overrides: Partial<DailyReviewDataSnapshot> = {}): DailyReviewDataSnapshot {
  return {
    indices: [
      { code: "000001", name: "上证指数", change_pct: 1.24 },
      { code: "399001", name: "深证成指", change_pct: -0.86 },
    ],
    hot_stocks: [],
    hot_concepts: [],
    hot_industries: [],
    dragon_tiger: [],
    market_statistics: {
      up_count: 3210,
      down_count: 1680,
      flat_count: 132,
      limit_up_count: 76,
      limit_down_count: 8,
    },
    market_news: [],
    top_sectors: [{ name: "机器人", change_pct: 4.28 }],
    bottom_sectors: [{ name: "煤炭", change_pct: -2.14 }],
    market_volume: {
      amount: 1_250_000_000_000,
      amount_before_one_day: 1_100_000_000_000,
      amount_average_60_day: 980_000_000_000,
    },
    macro_data: {},
    ...overrides,
  };
}

describe("DailyReviewCharts", () => {
  it("renders breadth, index, sector and volume charts from the snapshot", () => {
    render(<DailyReviewCharts snapshot={createSnapshot()} />);

    expect(screen.getByTestId("daily-review-breadth-chart")).toBeInTheDocument();
    expect(screen.getByTestId("daily-review-index-chart")).toBeInTheDocument();
    expect(screen.getByTestId("daily-review-sector-chart")).toBeInTheDocument();
    expect(screen.getByTestId("daily-review-volume-chart")).toBeInTheDocument();
    expect(screen.getByText("3,210 家")).toHaveAttribute("fill", expect.stringContaining("var(--c-text-primary"));
    expect(screen.getByText("上证指数")).toBeInTheDocument();
    expect(screen.getByText("机器人")).toBeInTheDocument();
    expect(screen.getByText("煤炭")).toBeInTheDocument();
  });

  it("shows one clear empty state when no chart has usable data", () => {
    render(<DailyReviewCharts snapshot={createSnapshot({
      indices: [{ name: "无效指数", change_pct: "not-a-number" }],
      market_statistics: {},
      top_sectors: [],
      bottom_sectors: [],
      market_volume: {},
    })} />);

    expect(screen.getByText("暂无可视化数据")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    expect(document.body.textContent).not.toContain("NaN");
  });
});
