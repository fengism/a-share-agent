import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HKStockPageContent from "./HKStockPageContent";

const mocks = vi.hoisted(() => ({
  addWatchlist: vi.fn(),
  deleteWatchlist: vi.fn(),
  navigate: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mocks.navigate,
  };
});

vi.mock("../../api/queryHooks/hk", () => ({
  useHKStockQuote: (code: string) => ({
    data: {
      code,
      name: "腾讯控股",
      english_name: "TENCENT",
      price: 385.4,
      change: 8.2,
      change_pct: 2.17,
      open: 380.0,
      pre_close: 377.2,
      high: 388.0,
      low: 379.4,
      volume: 18500000,
      amount: 7100000000,
      bid: 385.2,
      ask: 385.4,
      updated_at: "2026-03-30 16:00:00",
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useHKStockHistory: (_code: string, period: string, adjust: string) => ({
    data: {
      items: [
        {
          date: "2026-03-30",
          open: 380.0,
          close: 385.4,
          high: 388.0,
          low: 379.4,
          volume: 18500000,
          amount: 7100000000,
          amplitude: 2.28,
          turnover_pct: 0.2,
          change_pct: 2.17,
        },
      ],
      period,
      adjust,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../../api/queryHooks/watchlist", () => ({
  useWatchlist: () => ({
    data: {
      items: [
        { id: 1, stock_code: "600519", stock_name: "贵州茅台", market: "cn", note: "" },
      ],
    },
    isLoading: false,
  }),
  useAddWatchlistItem: () => ({
    mutateAsync: mocks.addWatchlist,
    isPending: false,
  }),
  useDeleteWatchlistItem: () => ({
    mutateAsync: mocks.deleteWatchlist,
    isPending: false,
  }),
}));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({ viewKey }: { viewKey: string }) => <div data-testid="kline-chart">{viewKey}</div>,
}));

describe("HKStockPageContent", () => {
  beforeEach(() => {
    mocks.addWatchlist.mockReset().mockResolvedValue(undefined);
    mocks.deleteWatchlist.mockReset().mockResolvedValue(undefined);
    mocks.navigate.mockReset();
  });

  it("renders HK stock quote details and trading rules", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: "腾讯控股" })).toBeInTheDocument();
    expect(screen.getByText("00700")).toBeInTheDocument();
    expect(screen.getByText("HK$385.40")).toBeInTheDocument();
    expect(screen.getByText("+8.20 (+2.17%)")).toBeInTheDocument();
    expect(screen.getByText("港股主板")).toBeInTheDocument();
    expect(screen.getByText("TENCENT")).toBeInTheDocument();
    expect(screen.getByText("T+0 回转交易 · 无单日涨跌幅限制")).toBeInTheDocument();
    expect(screen.getByTestId("kline-chart")).toBeInTheDocument();
  });

  it("adds HK stock to watchlist with market='hk'", async () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    const watchBtn = screen.getByRole("button", { name: "加入自选" });
    fireEvent.click(watchBtn);

    await waitFor(() => {
      expect(mocks.addWatchlist).toHaveBeenCalledWith({
        stock_code: "00700",
        market: "hk",
        note: "",
      });
    });
  });

  it("navigates to HK market overview on button click", () => {
    render(
      <MemoryRouter>
        <HKStockPageContent code="00700" />
      </MemoryRouter>,
    );

    const marketBtn = screen.getByRole("button", { name: "查看H股大盘市场" });
    fireEvent.click(marketBtn);

    expect(mocks.navigate).toHaveBeenCalledWith("/market?market=hk");
  });
});
