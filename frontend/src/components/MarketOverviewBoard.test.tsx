import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MarketOverviewBoard from "./MarketOverviewBoard";

const mocks = vi.hoisted(() => ({
  refetches: Array.from({ length: 5 }, () => vi.fn()),
  useMarketIndices: vi.fn(),
  useMarketEmotion: vi.fn(),
  useMarketLimitUpLadder: vi.fn(),
  useIndustryRankings: vi.fn(),
  useThsHotConcept: vi.fn(),
}));

vi.mock("../api/queries", () => ({
  useMarketIndices: () => mocks.useMarketIndices(),
  useMarketEmotion: () => mocks.useMarketEmotion(),
  useMarketLimitUpLadder: (date: string) => mocks.useMarketLimitUpLadder(date),
  useIndustryRankings: (date: string) => mocks.useIndustryRankings(date),
  useThsHotConcept: () => mocks.useThsHotConcept(),
}));

function queryResult<T>(data: T, refetch: ReturnType<typeof vi.fn>) {
  return {
    data,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch,
  };
}

describe("MarketOverviewBoard", () => {
  beforeEach(() => {
    mocks.refetches.forEach((refetch) => refetch.mockReset().mockResolvedValue(undefined));
    mocks.useMarketIndices.mockReturnValue(queryResult({
      indices: [
        { code: "000001", name: "上证指数", price: 3288.12, change_pct: 0.68, amount: 500_000_000_000 },
        { code: "399001", name: "深证成指", price: 10450.3, change_pct: -0.22, amount: 620_000_000_000 },
      ],
    }, mocks.refetches[0]));
    mocks.useMarketEmotion.mockReturnValue(queryResult({
      source: "财联社",
      market_degree: 68,
      shsz_balance: "1.77万亿",
      shsz_balance_change_px: "+1932亿",
      up_ratio: "77.00%",
      up_open_num: 19,
      up_open_ratio: "57%",
      up_down_dis: {
        status: true,
        suspend_num: 0,
        up_num: 68,
        down_num: 2,
        rise_num: 3200,
        fall_num: 1800,
        flat_num: 147,
        down_10: 3,
        down_8: 8,
        down_6: 21,
        down_4: 86,
        down_2: 1682,
        up_2: 2700,
        up_4: 380,
        up_6: 82,
        up_8: 28,
        up_10: 10,
      },
    }, mocks.refetches[1]));
    mocks.useMarketLimitUpLadder.mockReturnValue(queryResult({
      stocks: [
        { code: "600001", name: "示例股份", board_count: 4, limit_up_time: "10:18:00", sector_name: "机器人" },
        { code: "000002", name: "创新科技", board_count: 2, limit_up_time: "09:45:00", sector_name: "人工智能" },
      ],
    }, mocks.refetches[2]));
    mocks.useIndustryRankings.mockReturnValue(queryResult({
      date: "2026-08-28",
      sectors: [
        { rank: 1, code: "BK001", name: "半导体", change_pct: 3.25, leader: "芯片龙头" },
        { rank: 2, code: "BK002", name: "证券", change_pct: 1.82, up_count: 42, down_count: 5 },
      ],
    }, mocks.refetches[3]));
    mocks.useThsHotConcept.mockReturnValue(queryResult([
      { rank: 1, code: "GN001", name: "机器人概念", change_pct: 4.2, hot_value: 128000, hot_tag: "持续活跃", tag: "" },
    ], mocks.refetches[4]));
  });

  it("renders a dense market snapshot from independent market data sources", () => {
    render(<MarketOverviewBoard onNavigate={vi.fn()} />);

    expect(screen.getByText("上证指数")).toBeInTheDocument();
    expect(screen.getByText("3288.12")).toBeInTheDocument();
    expect(screen.getByText("1.77万亿")).toBeInTheDocument();
    expect(screen.getAllByText("上涨").length).toBeGreaterThan(0);
    expect(screen.getAllByText("3200").length).toBeGreaterThan(0);
    expect(screen.getAllByText("1800").length).toBeGreaterThan(0);
    expect(screen.getByText("市场热度")).toBeInTheDocument();
    expect(screen.getByLabelText("市场热度 68")).toBeInTheDocument();
    expect(screen.getByLabelText("全市场涨跌结构")).toBeInTheDocument();
    expect(screen.getByText("全市场涨跌结构")).toBeInTheDocument();
    expect(screen.getByText(/平盘/)).toBeInTheDocument();
    expect(screen.getByText("147")).toBeInTheDocument();
    expect(screen.getByText("8%以上")).toBeInTheDocument();
    expect(screen.getByText("0%～2%")).toBeInTheDocument();
    expect(screen.getByText("1682")).toBeInTheDocument();
    expect(screen.getByText("2700")).toBeInTheDocument();
    expect(screen.getByText("涨停梯队")).toBeInTheDocument();
    expect(screen.getByText("示例股份")).toBeInTheDocument();
    expect(screen.getByText("行业强弱")).toBeInTheDocument();
    expect(screen.getByText("半导体")).toBeInTheDocument();
    expect(screen.getByText("热门概念")).toBeInTheDocument();
    expect(screen.getByText("机器人概念")).toBeInTheDocument();
    expect(screen.queryByText("北向资金")).not.toBeInTheDocument();
    expect(screen.queryByText("交易日历")).not.toBeInTheDocument();
  });

  it("can hide ranking panels for the dashboard while keeping the component default", () => {
    render(<MarketOverviewBoard onNavigate={vi.fn()} showRankings={false} />);

    expect(screen.getByText("市场情绪")).toBeInTheDocument();
    expect(screen.getByText("涨停梯队")).toBeInTheDocument();
    expect(screen.queryByText("行业强弱")).not.toBeInTheDocument();
    expect(screen.queryByText("热门概念")).not.toBeInTheDocument();
  });

  it("navigates to detailed tabs and refreshes every snapshot query", () => {
    const onNavigate = vi.fn();
    render(<MarketOverviewBoard onNavigate={onNavigate} />);

    fireEvent.click(screen.getByRole("button", { name: /上证指数/ }));
    expect(onNavigate).toHaveBeenLastCalledWith("a-index");

    fireEvent.click(screen.getByRole("button", { name: "查看市场情绪详情" }));
    expect(onNavigate).toHaveBeenLastCalledWith("emotion");

    fireEvent.click(screen.getByRole("button", { name: "查看涨停梯队详情" }));
    expect(onNavigate).toHaveBeenLastCalledWith("limit-up");

    fireEvent.click(screen.getByRole("button", { name: "查看行业强弱详情" }));
    expect(onNavigate).toHaveBeenLastCalledWith("industry-rank");

    fireEvent.click(screen.getByRole("button", { name: /刷新看板/ }));
    mocks.refetches.forEach((refetch) => expect(refetch).toHaveBeenCalledTimes(1));
  });
});
