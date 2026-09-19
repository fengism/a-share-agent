import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MarketBreadthTab from "./MarketBreadthTab";

vi.mock("../../api/queries", () => ({
  useMarketBreadth: () => ({
    data: {
      source: "本地计算",
      fetched_at: "2026-08-20T16:00:00+08:00",
      industries: ["半导体", "白酒", "银行"],
      dates: ["2026-08-18", "2026-08-19", "2026-08-20"],
      values: [
        [70, 80, 90],
        [40, 50, 60],
        [10, 20, 30],
      ],
      summaries: [
        { date: "2026-08-18", strong_industry_count: 2, total_industry_count: 3, strong_ratio: 66.7 },
        { date: "2026-08-19", strong_industry_count: 2, total_industry_count: 3, strong_ratio: 66.7 },
        { date: "2026-08-20", strong_industry_count: 2, total_industry_count: 3, strong_ratio: 66.7 },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="breadth-chart" />,
}));

describe("MarketBreadthTab", () => {
  it("renders summary metrics and the breadth heatmap", () => {
    render(<MarketBreadthTab />);

    expect(screen.getByText("申万2级行业市场宽度热力图")).toBeInTheDocument();
    expect(screen.getByTestId("breadth-chart")).toBeInTheDocument();
    expect(screen.getByTestId("breadth-latest-date")).toHaveTextContent("2026-08-20");
    expect(screen.getByTestId("breadth-strong-ratio")).toHaveTextContent("66.7%");
    expect(screen.getByTestId("breadth-strong-count")).toHaveTextContent("2 / 3");
    expect(screen.getByTestId("breadth-state")).toHaveTextContent("偏强运行");
    expect(screen.getByText(/数据截至：2026-08-20/)).toBeInTheDocument();
  });
});
