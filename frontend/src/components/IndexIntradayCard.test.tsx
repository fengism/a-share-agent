import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { deriveIndexPrevClose } from "../utils/indexIntraday";
import IndexIntradayCard from "./IndexIntradayCard";

vi.mock("../api/queries", () => ({
  useMarketIndexIntraday: () => ({
    data: {
      code: "000001",
      source: "sina_direct",
      prev_close: null,
      items: [
        { time: "09:30:00", price: 3200, avg_price: 3199, volume: 100 },
        { time: "09:31:00", price: 3202, avg_price: 3200, volume: 80 },
      ],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../charts/IntradayChart", () => ({ default: () => <div>分时图表</div> }));

describe("IndexIntradayCard", () => {
  it("derives the previous close from the current quote", () => {
    expect(deriveIndexPrevClose(3200, 0.5)).toBeCloseTo(3184.0796, 4);
    expect(deriveIndexPrevClose(null, 0.5)).toBeNull();
    expect(deriveIndexPrevClose(3200, null)).toBeNull();
    expect(deriveIndexPrevClose(3200, -100)).toBeNull();
  });

  it("prioritizes the latest quote and chart legend", () => {
    render(
      <IndexIntradayCard
        symbol="000001"
        name="上证指数"
        price={3202}
        changePct={0.5}
      />,
    );

    expect(screen.getByText("上证指数 分时")).toBeInTheDocument();
    expect(screen.getByText("3202.00")).toBeInTheDocument();
    expect(screen.getByLabelText("上涨 0.50%")).toBeInTheDocument();
    expect(screen.getByText("更新 09:31")).toBeInTheDocument();
    expect(screen.getByText("价格")).toBeInTheDocument();
    expect(screen.getByText("均价")).toBeInTheDocument();
    expect(screen.getByText("成交量")).toBeInTheDocument();
    expect(screen.getByText("新浪财经")).toBeInTheDocument();
    expect(screen.getByText("分时图表")).toBeInTheDocument();
  });
});
