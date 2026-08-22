import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import LimitHistoryPanel from "./LimitHistoryPanel";

const mocks = vi.hoisted(() => ({ query: vi.fn() }));

vi.mock("../../api/queries", () => ({
  useMarketLimitHistory: (date: string, category: string) => {
    mocks.query(date, category);
    return {
      data: {
        source: "开盘红",
        date: "2026-08-20",
        category: "limit_down",
        fetched_at: "2026-08-21T08:00:00+00:00",
        total: 1,
        items: [
          {
            code: "600376",
            name: "首开股份",
            limit_time: "14:24:37",
            open_time: "",
            seal_amount: 5_023_161,
            limit_tag: "",
            limit_count: 0,
            themes: "房地产、地产链",
            net_inflow: -29_382_611,
            turnover: 526_093_870,
            turnover_rate: 12.12,
            market_cap: 4_286_293_311,
            reason: "",
            seal_money: 0,
            industry_id: "",
            industry_limit_up_count: 0,
          },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    };
  },
}));

describe("LimitHistoryPanel", () => {
  it("renders the selected historical limit-down list with category-specific columns", () => {
    render(
      <MemoryRouter initialEntries={["/market?tab=limit-up&mode=history&historyCategory=limit_down&historyDate=2026-08-20"]}>
        <LimitHistoryPanel />
      </MemoryRouter>,
    );

    expect(mocks.query).toHaveBeenCalledWith("2026-08-20", "limit_down");
    expect(screen.getAllByText("历史跌停").length).toBeGreaterThan(0);
    expect(screen.getByText("数据日期：2026-08-20")).toBeInTheDocument();
    expect(screen.getByText("首开股份")).toBeInTheDocument();
    expect(screen.getAllByText("跌停时间").length).toBeGreaterThan(0);
    expect(screen.getByText("房地产、地产链")).toBeInTheDocument();
    expect(screen.queryByText("连板标签")).not.toBeInTheDocument();
    expect(screen.queryByText("涨停原因")).not.toBeInTheDocument();
  });
});
