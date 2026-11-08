import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LeekIndexPage from "./index";
import * as sentimentHooks from "../../api/queryHooks/sentiment";

const mockOverview: sentimentHooks.LeekIndexOverviewResponse = {
  trade_date: "2026-11-08",
  updated_at: "2026-11-08 15:30:00",
  summary: {
    median_score: 45.0,
    extreme_count: 1,
    fever_count: 2,
    safe_count: 3,
    market_sentiment_label: "全市场博弈均衡",
  },
  industries: [
    {
      industry_name: "电子",
      leek_score: 86.5,
      risk_level: "extreme",
      sub_scores: { flow: 90, guba: 100, crowd: 70, trap: 85 },
      change_pct: -3.5,
      main_net: -500000000,
      retail_net: 600000000,
      crowded_stocks: [
        { code: "603366", name: "日出东方", rank: 1, change_pct: 10.0, reason: "股吧人气Top1" },
      ],
      warning_signals: ["散户逆势重仓补仓"],
    },
    {
      industry_name: "银行",
      leek_score: 28.0,
      risk_level: "safe",
      sub_scores: { flow: 20, guba: 15, crowd: 30, trap: 25 },
      change_pct: 1.2,
      main_net: 300000000,
      retail_net: -200000000,
      crowded_stocks: [],
      warning_signals: [],
    },
  ],
};

describe("LeekIndexPage", () => {
  it("renders overview summary and industry list correctly", () => {
    vi.spyOn(sentimentHooks, "useLeekIndexOverview").mockReturnValue({
      data: mockOverview,
      isLoading: false,
      isFetching: false,
    } as unknown as ReturnType<typeof sentimentHooks.useLeekIndexOverview>);

    vi.spyOn(sentimentHooks, "useIndustryLeekHistory").mockReturnValue({
      data: { industry_name: "电子", history: [] },
      isLoading: false,
    } as unknown as ReturnType<typeof sentimentHooks.useIndustryLeekHistory>);

    vi.spyOn(sentimentHooks, "useRefreshLeekIndex").mockReturnValue({
      mutate: vi.fn(),
      isPending: false,
    } as unknown as ReturnType<typeof sentimentHooks.useRefreshLeekIndex>);

    const queryClient = new QueryClient();
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <LeekIndexPage />
        </BrowserRouter>
      </QueryClientProvider>
    );

    // 验证标题与总体指标
    expect(screen.getByText("A股行业韭菜指数看板")).toBeInTheDocument();
    expect(screen.getByText("全市场博弈均衡", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("电子")).toBeInTheDocument();
    expect(screen.getByText("银行")).toBeInTheDocument();
    expect(screen.getByText("86.5")).toBeInTheDocument();
    expect(screen.getByText("日出东方")).toBeInTheDocument();

    // 点击电子行业链接，验证抽屉弹出
    fireEvent.click(screen.getByText("电子"));
    expect(screen.getByText(/散户博弈与韭菜指数详情/)).toBeInTheDocument();
    expect(screen.getByText("资金流背离（主力跑/散户买剪刀差）")).toBeInTheDocument();
  });
});
