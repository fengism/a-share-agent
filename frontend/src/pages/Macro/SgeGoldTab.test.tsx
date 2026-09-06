import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SgeGoldTab from "./SgeGoldTab";

const mocks = vi.hoisted(() => ({
  useSgeGoldHistory: vi.fn(),
  chart: vi.fn(() => <div data-testid="gold-kline" />),
}));

vi.mock("../../api/queries", () => ({
  useSgeGoldHistory: mocks.useSgeGoldHistory,
}));

vi.mock("echarts-for-react", () => ({
  default: mocks.chart,
}));

const history = [
  { date: "2026-08-01", open: 800, close: 805, low: 798, high: 808, change: null, change_pct: null },
  { date: "2026-09-02", open: 810.5, close: 812.3, low: 808, high: 815, change: 7.3, change_pct: 0.91 },
];

describe("SgeGoldTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.useSgeGoldHistory.mockImplementation((symbol: string) => ({
      data: {
        symbol,
        name: symbol === "Ag(T+D)" ? "白银 Ag(T+D)" : "黄金 Au99.99",
        unit: symbol === "Ag(T+D)" ? "元/千克" : "元/克",
        source: "上海黄金交易所",
        latest: history[1],
        history,
        updated_at: "2026-09-03T08:00:00+08:00",
        is_stale: false,
      },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    }));
  });

  it("renders latest quote and candlestick series", () => {
    render(<SgeGoldTab />);

    expect(mocks.useSgeGoldHistory).toHaveBeenCalledWith("Au99.99");
    expect(screen.getByText("812.30")).toBeInTheDocument();
    expect(screen.getByText("+0.91%")).toBeInTheDocument();
    expect(screen.getByText("808.00 / 815.00")).toBeInTheDocument();
    expect(screen.getByTestId("gold-kline")).toBeInTheDocument();
    expect(mocks.chart).toHaveBeenCalledWith(
      expect.objectContaining({
        option: expect.objectContaining({
          series: [expect.objectContaining({ type: "candlestick" })],
        }),
      }),
      expect.anything(),
    );
  });

  it("requests the newly selected SGE symbol", () => {
    render(<SgeGoldTab />);

    fireEvent.change(screen.getByLabelText("黄金品种"), { target: { value: "Ag(T+D)" } });

    expect(mocks.useSgeGoldHistory).toHaveBeenLastCalledWith("Ag(T+D)");
    expect(screen.getByText("白银 Ag(T+D)")).toBeInTheDocument();
  });
});
