import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IndustryRankTab from "./IndustryRankTab";

const baselineRankingData = {
  source: "开盘红",
  date: "2026-08-20",
  fetched_at: "2026-08-21T08:00:00+00:00",
  fund_data_available: true,
  total: 1,
  sectors: [
    {
      rank: 1,
      name: "贵金属",
      change_pct: 5.338,
      code: "881169",
      up_count: null,
      down_count: null,
      leader: "",
      leader_change: null,
      amount: 47_051_213_914,
      net_inflow: 3_885_676_376,
      buy_amount: 19_932_149_027,
      sell_amount: -16_046_472_651,
      turnover_rate: 1.526,
      market_cap: 1_354_185_084_652,
      avg_change: 3.79,
    },
  ],
};

const mocks = vi.hoisted(() => ({
  query: vi.fn(),
  stocksQuery: vi.fn(),
  rankingData: {
    source: "开盘红",
    date: "2026-08-20",
    fetched_at: "2026-08-21T08:00:00+00:00",
    fund_data_available: true,
    total: 1,
    sectors: [
      {
        rank: 1,
        name: "贵金属",
        change_pct: 5.338,
        code: "881169",
        up_count: null,
        down_count: null,
        leader: "",
        leader_change: null,
        amount: 47_051_213_914,
        net_inflow: 3_885_676_376,
        buy_amount: 19_932_149_027,
        sell_amount: -16_046_472_651,
        turnover_rate: 1.526,
        market_cap: 1_354_185_084_652,
        avg_change: 3.79,
      },
    ],
  },
}));

vi.mock("../../api/queries", () => ({
  useIndustryRankings: (date: string) => {
    mocks.query(date);
    return {
      data: mocks.rankingData,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    };
  },
  useMarketSectorStocksHistory: (date: string, plateId: string) => {
    mocks.stocksQuery(date, plateId);
    const isToday = date === new Date().toLocaleDateString("sv-SE");
    return {
      data: {
        source: "开盘红",
        date,
        constituent_date: isToday ? "2026-09-18" : date,
        plate_id: "881169",
        fetched_at: "2026-08-21T08:00:00+00:00",
        quoted_at: isToday ? "2026-09-19T10:15:00" : null,
        quote_source: isToday ? "tencent" : null,
        is_realtime: isToday,
        realtime_partial: false,
        history_details_available: !isToday,
        total: 1,
        items: [
          {
            code: "600732",
            name: "爱旭股份",
            tags: "光伏概念、BC电池",
            price: 12.35,
            change_pct: 10.02,
            amount: 1_234_567_890,
            turnover_rate: isToday ? null : 8.66,
            float_amount: isToday ? null : 22_000_000_000,
            main_buy: isToday ? null : 320_000_000,
            main_sell: isToday ? null : 210_000_000,
            main_net: isToday ? null : 110_000_000,
            buy_ratio: isToday ? null : 45.2,
            sell_ratio: isToday ? null : 29.7,
            net_ratio: isToday ? null : 15.5,
            limit_tag: isToday ? "" : "首板",
            rank_tag: isToday ? "" : "龙一",
            recent_chg: isToday ? null : 25.3,
            limit_count: isToday ? null : 2,
            chg_1d: isToday ? null : 10.02,
            chg_5d: isToday ? null : 18.4,
            chg_20d: isToday ? null : 32.1,
            quote_source: isToday ? "tencent" : null,
            quoted_at: isToday ? "2026-09-19T10:15:00" : null,
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

function renderTab(initialUrl: string) {
  return render(
    <MemoryRouter initialEntries={[initialUrl]}>
      <IndustryRankTab />
    </MemoryRouter>,
  );
}

describe("IndustryRankTab", () => {
  beforeEach(() => {
    mocks.rankingData = baselineRankingData;
    mocks.query.mockClear();
    mocks.stocksQuery.mockClear();
  });

  afterEach(() => {
    mocks.rankingData = baselineRankingData;
  });

  it("shows Kaipanhong industry fund flows for the selected historical date", () => {
    renderTab("/market?tab=industry-rank&industryDate=2026-08-20");

    expect(mocks.query).toHaveBeenCalledWith("2026-08-20");
    expect(screen.getByText("开盘红")).toBeInTheDocument();
    expect(screen.getByText("数据日期：2026-08-20")).toBeInTheDocument();
    expect(screen.getByText("贵金属")).toBeInTheDocument();
    expect(screen.getAllByText("涨跌幅").length).toBeGreaterThan(0);
    expect(screen.getAllByText("净流入").length).toBeGreaterThan(0);
    expect(screen.queryByLabelText("行业排行视图")).not.toBeInTheDocument();
    expect(screen.getByText("38.9亿")).toBeInTheDocument();
    expect(screen.getByText("-160.5亿")).toBeInTheDocument();
  });

  it("opens the sector stocks drawer for a historical date", async () => {
    renderTab("/market?tab=industry-rank&industryDate=2026-08-20");

    const action = screen.getAllByRole("button", { name: "成分股" })[0];
    expect(action).toBeEnabled();
    fireEvent.click(action);

    await screen.findByText(/贵金属 成分股 · 2026-08-20/);
    expect(mocks.stocksQuery).toHaveBeenCalledWith("2026-08-20", "881169");
    expect(screen.getByText("爱旭股份")).toBeInTheDocument();
    expect(screen.getByText("首板 · 2板")).toBeInTheDocument();
  });

  it("uses the resolved trading date for weekend data and sector drill-down", async () => {
    mocks.rankingData = {
      ...baselineRankingData,
      date: "2026-08-21",
    };
    renderTab("/market?tab=industry-rank&industryDate=2026-08-22");

    expect(mocks.query).toHaveBeenCalledWith("2026-08-22");
    expect(screen.getByText("数据日期：2026-08-21")).toBeInTheDocument();
    expect(screen.getByText("已回退至最近交易日")).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole("button", { name: "成分股" })[0]);

    await screen.findByText(/贵金属 成分股 · 2026-08-21/);
    expect(mocks.stocksQuery).toHaveBeenCalledWith("2026-08-21", "881169");
  });

  it("opens the latest sector stocks with historical constituent context for today", async () => {
    const today = new Date().toLocaleDateString("sv-SE");
    mocks.rankingData = {
      ...baselineRankingData,
      date: today,
    };
    renderTab(`/market?tab=industry-rank&industryDate=${today}`);

    const action = screen.getAllByRole("button", { name: "成分股" })[0];
    expect(action).toBeEnabled();
    fireEvent.click(action);

    await screen.findByText(new RegExp(`贵金属 成分股 · ${today}`));
    expect(mocks.stocksQuery).toHaveBeenCalledWith(today, "881169");
    expect(screen.getByText("成分口径：开盘红 2026-09-18")).toBeInTheDocument();
    expect(screen.getByText("行情时间：2026-09-19T10:15:00")).toBeInTheDocument();
    const drawer = within(screen.getByRole("dialog"));
    expect(drawer.getAllByText("现价").length).toBeGreaterThan(0);
    expect(drawer.getAllByText("成交额").length).toBeGreaterThan(0);
    expect(drawer.getByText("12.35")).toBeInTheDocument();
    expect(drawer.getByText("12.3亿")).toBeInTheDocument();
    expect(drawer.queryByText("主力净额")).not.toBeInTheDocument();
    expect(drawer.queryByText("换手率")).not.toBeInTheDocument();
    expect(drawer.queryByText("流通市值")).not.toBeInTheDocument();
    expect(drawer.queryByText("连板标签")).not.toBeInTheDocument();
    expect(drawer.queryByText("龙虎榜")).not.toBeInTheDocument();
  });

  it("disables the drill-down action when rankings come from a fallback source", () => {
    mocks.rankingData = {
      ...baselineRankingData,
      source: "财联社",
      fund_data_available: false,
    };
    renderTab("/market?tab=industry-rank&industryDate=2026-08-20");

    const actions = screen.getAllByRole("button", { name: "成分股" });
    for (const action of actions) {
      expect(action).toBeDisabled();
    }
    expect(mocks.stocksQuery).not.toHaveBeenCalledWith("2026-08-20", "881169");
  });
});
