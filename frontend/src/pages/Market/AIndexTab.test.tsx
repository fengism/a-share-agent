import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AIndexTab from "./AIndexTab";

const mocks = vi.hoisted(() => {
  const defaultIndices = [
    { code: "000001", name: "上证指数", price: 3200, change_pct: 0.5, amount: 100000000 },
    { code: "399001", name: "深证成指", price: 11000, change_pct: -0.2, amount: 200000000 },
  ];
  return { kline: vi.fn(), intraday: vi.fn(), indices: [...defaultIndices], defaultIndices };
});

vi.mock("../../api/queries", () => ({
  useMarketIndices: () => ({
    data: {
      indices: mocks.indices,
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketIndexIntraday: (symbol: string) => {
    mocks.intraday(symbol);
    return {
      data: { code: symbol, source: "sina_direct", prev_close: null, items: [{ time: "09:30:00", price: 3200, avg_price: 3199, volume: 10 }] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    };
  },
  useMarketIndexKline: (symbol: string, period: string, options?: { startDate?: string }) => {
    mocks.kline(symbol, period, options);
    return {
      data: { items: [{ date: "2026-08-12", open: 1, close: 2, high: 2, low: 1, volume: 10 }] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    };
  },
  useMarketVolume: () => ({
    data: { items: [] },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="echarts-mock" />,
}));
vi.mock("../../charts/echarts-setup", () => ({ default: {} }));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({
    viewKey,
    onReachLeftEdge,
    historyLimitReached,
  }: {
    viewKey?: string;
    onReachLeftEdge?: () => void;
    historyLimitReached?: boolean;
  }) => (
    <div data-testid="lazy-kline-chart" data-view-key={viewKey}>
      <span>指数K线图</span>
      {onReachLeftEdge ? (
        <button type="button" data-testid="kline-expand-history" onClick={onReachLeftEdge}>
          向左滑动
        </button>
      ) : null}
      <span data-testid="kline-history-limit">{historyLimitReached ? "limit" : "more"}</span>
    </div>
  ),
}));
vi.mock("../../charts/IntradayChart", () => ({
  default: () => <div>指数分时图</div>,
}));

function LocationProbe() {
  return <div data-testid="location-search">{useLocation().search}</div>;
}

describe("AIndexTab", () => {
  beforeEach(() => {
    mocks.kline.mockReset();
    mocks.intraday.mockReset();
    mocks.indices = [...mocks.defaultIndices];
  });

  it("restores index and period from the URL and keeps changes shareable", async () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=a-index&index=399001&period=weekly"]}>
        <AIndexTab />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(mocks.kline).toHaveBeenCalledWith("399001", "weekly", { startDate: expect.any(String), liveRefresh: false });
    expect(mocks.intraday).toHaveBeenCalledWith("399001");
    expect(screen.getByText("指数分时图")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /深证成指/ })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /上证指数/ }));
    await waitFor(() => expect(mocks.kline).toHaveBeenCalledWith("000001", "weekly", { startDate: expect.any(String), liveRefresh: false }));
    await waitFor(() => expect(mocks.intraday).toHaveBeenCalledWith("000001"));
    expect(screen.getByTestId("location-search")).not.toHaveTextContent("index=");

    fireEvent.click(screen.getByText("月K"));
    await waitFor(() => expect(mocks.kline).toHaveBeenCalledWith("000001", "monthly", { startDate: expect.any(String), liveRefresh: false }));
    expect(screen.getByTestId("location-search")).toHaveTextContent("period=monthly");
  });

  it("renders four returned indices as a full row and resets a missing selection", async () => {
    mocks.indices = [
      ...mocks.defaultIndices,
      { code: "399006", name: "创业板指", price: 3500, change_pct: 0.8, amount: 150000000 },
      { code: "000300", name: "沪深300", price: 4600, change_pct: 0.1, amount: 180000000 },
    ];

    render(
      <MemoryRouter initialEntries={["/market?tab=a-index&index=000905"]}>
        <AIndexTab />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getAllByRole("button", { name: /指数|成指|创业板|沪深300/ })).toHaveLength(4);
    expect(screen.queryByText("中证500")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("button", { name: /上证指数/ })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByRole("button", { name: /上证指数/ }).closest(".ant-col")).toHaveClass("ant-col-lg-6");
    expect(screen.getByTestId("location-search")).not.toHaveTextContent("index=");
    expect(mocks.kline).toHaveBeenLastCalledWith("000001", "daily", { startDate: expect.any(String), liveRefresh: true });
  });

  it("defaults to one year of history and extends by one year per left-edge request up to ten years", async () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=a-index&index=000001"]}>
        <AIndexTab />
      </MemoryRouter>,
    );

    const rangeHint = () => screen.getByTestId("index-kline-history-range").textContent ?? "";
    expect(rangeHint()).toContain("近 1 年");
    expect(rangeHint()).toContain("最多 10 年");

    // 左缘触底逐年前扩，最多 10 年
    for (let years = 2; years <= 10; years += 1) {
      fireEvent.click(screen.getByTestId("kline-expand-history"));
      expect(rangeHint()).toContain(years === 10 ? "已加载近 10 年" : `近 ${years} 年`);
    }
    // 到达上限后不再挂载扩充按钮
    expect(screen.queryByTestId("kline-expand-history")).not.toBeInTheDocument();
  });

  it("resets the history window when index or period changes", async () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=a-index&index=000001"]}>
        <AIndexTab />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByTestId("kline-expand-history"));
    expect(screen.getByTestId("index-kline-history-range")).toHaveTextContent("近 2 年");

    fireEvent.click(screen.getByText("周K"));
    expect(screen.getByTestId("index-kline-history-range")).toHaveTextContent("近 1 年");
  });

  it("renders market volume trend card within AIndexTab", () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=a-index"]}>
        <AIndexTab />
      </MemoryRouter>,
    );
    expect(screen.getByText("A股全市场成交额走势")).toBeInTheDocument();
    expect(screen.getByText("沪深北全市场合计")).toBeInTheDocument();
  });
});
