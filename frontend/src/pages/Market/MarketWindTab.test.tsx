import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MarketWindTab from "./MarketWindTab";

const mocks = vi.hoisted(() => ({
  stocks: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMarketWind: () => ({
    data: {
      source: "财联社",
      fetched_at: "2026-08-13T10:30:00+08:00",
      items: [
        { plate_code: "cls80044", plate_name: "创新药", catalyst: "创新药投融资逐步修复。" },
        { plate_code: "cls82580", plate_name: "IDC电源", catalyst: "AI服务器电源需求快速增长。" },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketWindStocks: (plateCode: string) => mocks.stocks(plateCode),
}));

describe("MarketWindTab", () => {
  beforeEach(() => {
    mocks.stocks.mockImplementation((plateCode: string) => ({
      data: {
        source: "财联社",
        fetched_at: "2026-08-13T10:30:00+08:00",
        plate_code: plateCode,
        items: plateCode === "cls82580"
          ? [{ code: "300153", name: "科泰电源", price: 28.5, change_pct: 12.3, limit_up_days: 1 }]
          : [{ code: "688265", name: "南模生物", price: 52.42, change_pct: 20.01, limit_up_days: 2 }],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    }));
  });

  it("shows wind catalysts and switches leader stocks by plate", async () => {
    function LocationProbe() {
      return <div data-testid="location-search">{useLocation().search}</div>;
    }

    render(
      <MemoryRouter initialEntries={["/market?tab=today-wind"]}>
        <MarketWindTab />
        <LocationProbe />
      </MemoryRouter>,
    );

    expect(screen.getByText("今日风口")).toBeInTheDocument();
    expect(screen.getByText("今日主线速览")).toBeInTheDocument();
    expect(screen.getByText("当前聚焦")).toBeInTheDocument();
    expect(screen.getAllByText("创新药投融资逐步修复。").length).toBeGreaterThan(0);
    expect(await screen.findByText("南模生物")).toBeInTheDocument();
    expect(screen.getByText("数据来源：财联社")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择风口 创新药" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("最高涨幅")).toBeInTheDocument();
    expect(screen.getByText("20.01%")).toBeInTheDocument();
    expect(screen.getByText("2 板")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /南模生物/ })).toHaveAttribute(
      "href",
      "https://data.eastmoney.com/stockdata/688265.html",
    );

    fireEvent.click(screen.getByRole("button", { name: "选择风口 IDC电源" }));

    await waitFor(() => expect(mocks.stocks).toHaveBeenCalledWith("cls82580"));
    expect(screen.getByTestId("location-search")).toHaveTextContent("plate=cls82580");
    expect(await screen.findByText("科泰电源")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "选择风口 IDC电源" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("12.30%")).toBeInTheDocument();
  });
});
