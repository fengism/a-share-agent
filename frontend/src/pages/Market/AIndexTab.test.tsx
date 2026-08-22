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
  useMarketIndexKline: (symbol: string, period: string) => {
    mocks.kline(symbol, period);
    return {
      data: { items: [{ date: "2026-08-12", open: 1, close: 2, high: 2, low: 1, volume: 10 }] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    };
  },
}));

vi.mock("../../charts/LazyKlineChart", () => ({
  default: () => <div>指数K线图</div>,
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

    expect(mocks.kline).toHaveBeenCalledWith("399001", "weekly");
    expect(mocks.intraday).toHaveBeenCalledWith("399001");
    expect(screen.getByText("指数分时图")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /深证成指/ })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /上证指数/ }));
    await waitFor(() => expect(mocks.kline).toHaveBeenCalledWith("000001", "weekly"));
    await waitFor(() => expect(mocks.intraday).toHaveBeenCalledWith("000001"));
    expect(screen.getByTestId("location-search")).not.toHaveTextContent("index=");

    fireEvent.click(screen.getByText("月K"));
    await waitFor(() => expect(mocks.kline).toHaveBeenCalledWith("000001", "monthly"));
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
    expect(mocks.kline).toHaveBeenLastCalledWith("000001", "daily");
  });
});
