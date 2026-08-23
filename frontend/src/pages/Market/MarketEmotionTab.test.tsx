import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import MarketEmotionTab from "./MarketEmotionTab";

const mocks = vi.hoisted(() => ({
  useMarketEmotion: vi.fn(),
}));

vi.mock("../../api/queries", () => ({
  useMarketEmotion: () => mocks.useMarketEmotion(),
}));

describe("MarketEmotionTab", () => {
  beforeEach(() => {
    mocks.useMarketEmotion.mockReturnValue({
      data: {
        source: "财联社",
        fetched_at: "2026-08-13T10:30:00+08:00",
        market_degree: 37,
        shsz_balance: "1.77万亿",
        shsz_balance_change_px: "+1932亿",
        preview_balance: "2.4万亿",
        preview_balance_change_px: "+2478亿",
        up_ratio: "77.00%",
        up_ratio_num: 67,
        up_open_num: 19,
        performance: "1.72%",
        up_open_ratio: "57%",
        profit_ratio: "53%",
        up_down_dis: {
          status: true,
          suspend_num: 3,
          up_num: 68,
          down_num: 0,
          rise_num: 2194,
          fall_num: 3202,
          flat_num: 147,
          down_10: 6,
          down_8: 16,
          down_6: 50,
          down_4: 402,
          down_2: 2728,
          up_2: 1420,
          up_4: 443,
          up_6: 138,
          up_8: 73,
          up_10: 120,
        },
        limit_up_board: [
          { name: "一板", count: 46, promotion_rate: "16%" },
          { name: "二板", count: 12, promotion_rate: "29%" },
          { name: "三板", count: 2, promotion_rate: "78%" },
          { name: "高度板", count: 7, promotion_rate: null },
        ],
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("summarizes market mood before showing detailed indicators", () => {
    render(<MarketEmotionTab />);

    expect(screen.getByText("今日市场体感")).toBeInTheDocument();
    expect(screen.getByText("偏冷 · 个股跌多涨少")).toBeInTheDocument();
    expect(screen.getByText(/下跌家数比上涨多 1008 家/)).toBeInTheDocument();
    expect(screen.getByLabelText("市场热度 37")).toBeInTheDocument();
    expect(screen.getByText("成交活跃度")).toBeInTheDocument();
    expect(screen.getByText("1.77万亿")).toBeInTheDocument();
    expect(screen.getByText("2.4万亿")).toBeInTheDocument();
    expect(screen.getByText("短线赚钱效应")).toBeInTheDocument();
    expect(screen.getByText("全市场涨跌结构")).toBeInTheDocument();
    expect(screen.getAllByText("上涨占比 40.7%").length).toBeGreaterThan(0);
    expect(screen.getByText("上涨 2194")).toBeInTheDocument();
    expect(screen.getByText("下跌 3202")).toBeInTheDocument();
    expect(screen.getByText("连板梯队")).toBeInTheDocument();
    expect(screen.getByText("高度板")).toBeInTheDocument();
  });
});
