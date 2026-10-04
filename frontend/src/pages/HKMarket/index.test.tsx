import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import HKMarket from ".";

function LocationProbe() {
  const location = useLocation();
  return <span data-testid="location">{location.pathname}{location.search}</span>;
}

const mocks = vi.hoisted(() => ({
  useHKIndices: vi.fn(),
  useHKIndexHistory: vi.fn(),
  useHKStocks: vi.fn(),
  useHKStockSearch: vi.fn(),
  useHKStockHistory: vi.fn(),
  addWatchlistItem: vi.fn(),
}));

vi.mock("../../api/queryHooks/hk", () => ({
  useHKIndices: (...args: unknown[]) => mocks.useHKIndices(...args),
  useHKIndexHistory: (...args: unknown[]) => mocks.useHKIndexHistory(...args),
  useHKStocks: (...args: unknown[]) => mocks.useHKStocks(...args),
  useHKStockSearch: (...args: unknown[]) => mocks.useHKStockSearch(...args),
  useHKStockHistory: (...args: unknown[]) => mocks.useHKStockHistory(...args),
}));

vi.mock("../../api/queryHooks/watchlist", () => ({
  useAddWatchlistItem: () => ({
    mutateAsync: mocks.addWatchlistItem,
    isPending: false,
  }),
}));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({ data }: { data: unknown[] }) => <div data-testid="kline-chart">{data.length}根K线</div>,
}));

const idle = { isLoading: false, error: null, refetch: vi.fn() };

const stocks = [
  {
    code: "00700",
    name: "腾讯控股",
    price: 610.5,
    change_pct: 0.91,
    open: 606,
    high: 615,
    low: 602,
    volume: 1000,
    amount: 610500,
  },
  {
    code: "09988",
    name: "阿里巴巴-W",
    price: 132.2,
    change_pct: -0.45,
    open: 133,
    high: 134,
    low: 131.5,
    volume: 2000,
    amount: 264400,
  },
  { code: "00005", name: "汇丰控股", price: 105, change_pct: 0.2, open: 104, high: 106, low: 103, volume: 3000, amount: 315000 },
  { code: "00941", name: "中国移动", price: 86, change_pct: 0.1, open: 85, high: 87, low: 84, volume: 4000, amount: 344000 },
  { code: "01299", name: "友邦保险", price: 75, change_pct: -0.3, open: 76, high: 77, low: 74, volume: 5000, amount: 375000 },
  { code: "03690", name: "美团-W", price: 118, change_pct: 0.5, open: 117, high: 119, low: 116, volume: 6000, amount: 708000 },
];

describe("HKMarket", () => {
  beforeEach(() => {
    mocks.addWatchlistItem.mockReset().mockResolvedValue({});
    mocks.useHKIndices.mockReturnValue({
      ...idle,
      data: {
        source: "sina",
        indices: [
          { code: "HSI", name: "恒生指数", price: 25200, change_pct: 0.4 },
          { code: "HSCEI", name: "恒生中国企业指数", price: 9000, change_pct: -0.2 },
          { code: "HSTECH", name: "恒生科技指数", price: 5600, change_pct: 0.1 },
        ],
      },
    });
    mocks.useHKIndexHistory.mockReturnValue({
      ...idle,
      data: {
        items: [{ date: "2026-09-02", open: 1, high: 2, low: 1, close: 2, volume: 10, amount: 0 }],
      },
    });
    mocks.useHKStocks.mockReturnValue({
      ...idle,
      data: { total: stocks.length, page: 1, page_size: 50, source: "sina", items: stocks },
    });
    mocks.useHKStockHistory.mockReturnValue({ ...idle, data: { items: [] } });
    mocks.useHKStockSearch.mockReturnValue({
      ...idle,
      isFetching: false,
      isError: false,
      data: { items: [{ code: "00700", name: "腾讯控股", english_name: "TENCENT" }] },
    });
  });

  it("renders indices and navigates to stock profile on click", () => {
    render(
      <MemoryRouter initialEntries={["/market?market=hk"]}>
        <Routes>
          <Route path="/market" element={<HKMarket />} />
          <Route path="/stock/:code" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText("港股行情")).toBeInTheDocument();
    expect(screen.getByText("恒生科技指数")).toBeInTheDocument();
    fireEvent.click(screen.getByText("腾讯控股"));

    expect(screen.getByTestId("location")).toHaveTextContent("/stock/00700");
  });

  it("renders defaultStockCode and fetches stock history", () => {
    render(
      <MemoryRouter>
        <HKMarket defaultStockCode="00700" />
      </MemoryRouter>,
    );

    expect(mocks.useHKStockHistory).toHaveBeenLastCalledWith("00700", "daily", "qfq");
  });

  it("debounces indexed search and navigates to stock profile on select", async () => {
    render(
      <MemoryRouter initialEntries={["/market?market=hk"]}>
        <Routes>
          <Route path="/market" element={<HKMarket />} />
          <Route path="/stock/:code" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(mocks.useHKStocks).toHaveBeenLastCalledWith("", 1, 50);
    fireEvent.change(screen.getByRole("combobox", { name: "搜索港股" }), {
      target: { value: "腾讯" },
    });

    await waitFor(() => expect(mocks.useHKStockSearch).toHaveBeenLastCalledWith("腾讯"));
    fireEvent.click(await screen.findByText("TENCENT"));

    expect(screen.getByTestId("location")).toHaveTextContent("/stock/00700");
  });

  it("selects up to five stocks and renders the comparison table", () => {
    render(
      <MemoryRouter>
        <HKMarket />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "选择腾讯控股" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "选择阿里巴巴-W" }));

    expect(screen.getByText("已选 2/5")).toBeInTheDocument();
    expect(screen.getByText("港股对比 · 2 只")).toBeInTheDocument();
    expect(screen.getAllByText("腾讯控股").length).toBeGreaterThan(1);
    expect(screen.getAllByText("阿里巴巴-W").length).toBeGreaterThan(1);

    fireEvent.click(screen.getByRole("checkbox", { name: "选择腾讯控股" }));

    expect(screen.getByText("已选 1/5")).toBeInTheDocument();
    expect(screen.getByText("港股对比 · 1 只")).toBeInTheDocument();
  });

  it("limits comparison selection to five stocks", () => {
    render(
      <MemoryRouter>
        <HKMarket />
      </MemoryRouter>,
    );

    ["腾讯控股", "阿里巴巴-W", "汇丰控股", "中国移动", "友邦保险"].forEach((name) => {
      fireEvent.click(screen.getByRole("checkbox", { name: `选择${name}` }));
    });

    expect(screen.getByText("已选 5/5")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "选择美团-W" })).toBeDisabled();
  });

  it("adds every selected Hong Kong stock to the shared watchlist", async () => {
    render(
      <MemoryRouter>
        <HKMarket />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("checkbox", { name: "选择腾讯控股" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "选择阿里巴巴-W" }));
    fireEvent.click(screen.getByRole("button", { name: /加入自选/ }));

    await waitFor(() => expect(mocks.addWatchlistItem).toHaveBeenCalledTimes(2));
    expect(mocks.addWatchlistItem).toHaveBeenNthCalledWith(1, {
      stock_code: "00700",
      market: "hk",
      note: "",
    });
    expect(mocks.addWatchlistItem).toHaveBeenNthCalledWith(2, {
      stock_code: "09988",
      market: "hk",
      note: "",
    });
  });
});
