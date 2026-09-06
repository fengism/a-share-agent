import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import LimitUpLadderTab from "./LimitUpLadderTab";

const mocks = vi.hoisted(() => ({ query: vi.fn() }));

vi.mock("../../api/queries", () => ({
  useMarketLimitUpLadder: (date: string) => {
    mocks.query(date);
    return ({
    data: {
      source: "开盘红",
      date: "2026-08-12",
      fetched_at: "2026-08-13T10:30:00+08:00",
      total: 2,
      stocks: [
        {
          code: "600721",
          name: "百花医药",
          board_count: 7,
          limit_up_time: "09:33:45",
          sector_code: "801045",
          sector_name: "医药",
          one_word: false,
          popular: true,
          sector_limit_up_count: 8,
          amount: 5395203319,
          sector_amount: 8953769710,
        },
        {
          code: "603758",
          name: "秦安股份",
          board_count: 4,
          limit_up_time: "09:25:32",
          sector_code: "801159",
          sector_name: "机器人概念",
          one_word: true,
          popular: false,
          sector_limit_up_count: 7,
          amount: 6041968884,
          sector_amount: 4128318040,
        },
      ],
      sectors: [
        { sector_code: "801045", sector_name: "医药", stock_count: 8, amount: 8953769710, stock_codes: ["600721"] },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
    });
  },
}));

describe("LimitUpLadderTab", () => {
  it("shows the limit-up ladder and sector distribution", () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=limit-up&date=2026-08-12"]}>
        <LimitUpLadderTab />
      </MemoryRouter>,
    );

    expect(mocks.query).toHaveBeenCalledWith("2026-08-12");
    expect(screen.getByText("涨停板")).toBeInTheDocument();
    expect(screen.getAllByText("涨停天梯").length).toBeGreaterThan(0);
    expect(screen.getByText("历史复盘")).toBeInTheDocument();
    expect(screen.getByText("数据日期：2026-08-12")).toBeInTheDocument();
    expect(screen.getByText("百花医药")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /百花医药/ })).toHaveAttribute(
      "href",
      "/stock/600721",
    );
    expect(screen.getByText("7连板")).toBeInTheDocument();
    expect(screen.getAllByText("大单一字").length).toBeGreaterThan(0);
    expect(screen.getAllByText("人气股").length).toBeGreaterThan(0);
    expect(screen.getAllByText("医药").length).toBeGreaterThan(0);
  });
});
