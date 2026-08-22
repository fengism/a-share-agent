import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import BacktestTradeKline from "./BacktestTradeKline";

const mocks = vi.hoisted(() => ({ useKlineData: vi.fn() }));

vi.mock("../../../api/queries", () => ({ useKlineData: mocks.useKlineData }));
vi.mock("../../../hooks/useMediaQuery", () => ({ useMediaQuery: () => false }));
vi.mock("../../../charts/LazyKlineChart", () => ({
  default: ({ data, tradeMarkers, viewKey }: { data: unknown[]; tradeMarkers: unknown; viewKey: string }) => (
    <div data-testid="trade-kline" data-count={data.length} data-markers={JSON.stringify(tradeMarkers)} data-view-key={viewKey} />
  ),
}));

const trades = [
  { date: "2026-01-03", code: "600519", side: "buy" as const, price: 10, shares: 100, amount: 1000, fee: 1, realized_pnl: null },
  { date: "2026-01-05", code: "600519", side: "sell" as const, price: 12, shares: 100, amount: 1200, fee: 1, realized_pnl: 200 },
];

describe("BacktestTradeKline", () => {
  it("loads the backtest date range and renders buy/sell markers", () => {
    mocks.useKlineData.mockReturnValue({
      data: {
        source: "tencent",
        items: [{ date: "2026-01-03", open: 9, high: 11, low: 8, close: 10, volume: 100, amount: 1000 }],
      },
      isLoading: false,
      error: null,
    });

    render(<BacktestTradeKline
      codes={["600519"]}
      equityCurve={[{ date: "2026-01-02", equity: 1, benchmark: 1, drawdown: 0 }]}
      trades={trades}
    />);

    expect(screen.getByText("个股 K 线与买卖点")).toBeInTheDocument();
    expect(screen.getByText("↑ 买入")).toBeInTheDocument();
    expect(screen.getByText("↓ 卖出")).toBeInTheDocument();
    expect(screen.getByText("tencent")).toBeInTheDocument();
    expect(screen.getByTestId("trade-kline")).toHaveAttribute(
      "data-markers",
      JSON.stringify([
        { date: "2026-01-03", side: "buy", label: "买" },
        { date: "2026-01-05", side: "sell", label: "卖" },
      ]),
    );
    expect(mocks.useKlineData).toHaveBeenCalledWith(
      "600519",
      "daily",
      "qfq",
      true,
      { startDate: "20260102", endDate: "20260105" },
    );
  });

  it("shows an empty state when the strategy produced no trades", () => {
    mocks.useKlineData.mockReturnValue({ data: undefined, isLoading: false, error: null });

    render(<BacktestTradeKline codes={["600519"]} equityCurve={[]} trades={[]} />);

    expect(screen.getByText("本次回测没有买卖成交点")).toBeInTheDocument();
  });

  it("prefers the persisted backtest market snapshot over a fresh K-line request", () => {
    mocks.useKlineData.mockReturnValue({ data: undefined, isLoading: false, error: null });

    render(<BacktestTradeKline
      codes={["600519"]}
      equityCurve={[{ date: "2026-01-02", equity: 1, benchmark: 1, drawdown: 0 }]}
      trades={trades}
      marketSnapshots={[{
        code: "600519",
        source: "stock-source",
        data_hash: "stock-hash",
        items: [
          { code: "600519", date: "2025-12-31", open: 8, high: 9, low: 7, close: 8, volume: 100, amount: 800 },
          { code: "600519", date: "2026-01-03", open: 9, high: 11, low: 8, close: 10, volume: 100, amount: 1000 },
        ],
      }]}
    />);

    expect(screen.getByText("回测快照 · stock-source")).toBeInTheDocument();
    expect(screen.getByTestId("trade-kline")).toHaveAttribute("data-count", "1");
    expect(screen.getByTestId("trade-kline")).toHaveAttribute(
      "data-view-key",
      "backtest:600519:stock-hash:20260105",
    );
    expect(mocks.useKlineData).toHaveBeenCalledWith(
      "600519", "daily", "qfq", false, { startDate: "20260102", endDate: "20260105" },
    );
  });

});
