import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LeekIndexPage from "./index";
import * as sentimentHooks from "../../api/queryHooks/sentiment";
import * as csvUtils from "../../utils/csv";
import * as mediaQueryHooks from "../../hooks/useMediaQuery";

vi.mock("echarts-for-react/lib/core", () => ({
  default: ({ option }: { option?: { title?: { text?: string } } }) => (
    <div data-testid="leek-quadrant-chart" data-title={option?.title?.text} />
  ),
}));

vi.mock("../../utils/csv", () => ({
  downloadCsv: vi.fn(),
}));

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
      change_pct: 1.5,
      main_net: -500000000,
      retail_net: 600000000,
      crowded_stocks: [
        { code: "603366", name: "日出东方", rank: 1, change_pct: 10.0, reason: "股吧人气Top1" },
      ],
      warning_signals: ["散户逆势重仓补仓"],
      sub_industries: [
        {
          name: "半导体",
          leek_score: 88.0,
          change_pct: 2.1,
          main_net: -300000000,
          retail_net: 400000000,
        },
      ],
    },
    {
      industry_name: "银行",
      leek_score: 28.0,
      risk_level: "safe",
      sub_scores: { flow: 20, guba: 15, crowd: 30, trap: 25 },
      change_pct: -0.8,
      main_net: 300000000,
      retail_net: -200000000,
      crowded_stocks: [],
      warning_signals: [],
      sub_industries: [],
    },
  ],
};

describe("LeekIndexPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    vi.clearAllMocks();

    vi.spyOn(mediaQueryHooks, "useMediaQuery").mockReturnValue(false);

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
  });

  it("renders overview summary, industry list and drawer correctly", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
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

  it("toggles quadrant matrix chart view", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("行业博弈四象限矩阵")).toBeInTheDocument();
    expect(screen.getByTestId("leek-quadrant-chart")).toBeInTheDocument();

    const toggleBtn = screen.getByText("收起矩阵");
    fireEvent.click(toggleBtn);
    expect(screen.getByText("展开矩阵")).toBeInTheDocument();
    expect(screen.queryByTestId("leek-quadrant-chart")).not.toBeInTheDocument();

    fireEvent.click(screen.getByText("展开矩阵"));
    expect(screen.getByText("收起矩阵")).toBeInTheDocument();
    expect(screen.getByTestId("leek-quadrant-chart")).toBeInTheDocument();
  });

  it("triggers CSV export when clicking export button", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    const exportBtn = screen.getByText("导出 CSV");
    fireEvent.click(exportBtn);

    expect(csvUtils.downloadCsv).toHaveBeenCalledTimes(1);
    const [filename, rows] = vi.mocked(csvUtils.downloadCsv).mock.calls[0];
    expect(filename).toContain("A股行业韭菜指数_2026-11-08.csv");
    expect(rows.length).toBe(3); // header + 2 items
  });

  it("filters industries by quick presets", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // 点击 见顶预警 (>70且上涨): 电子(86.5, +1.5%)符合, 银行(28.0)不符合
    const topRiskTag = screen.getByText(/见顶预警/);
    fireEvent.click(topRiskTag);

    expect(screen.getByText("电子")).toBeInTheDocument();
    expect(screen.queryByText("银行")).not.toBeInTheDocument();

    // 点击 黄金坑探底 (<40且下跌): 银行(28.0, -0.8%)符合, 电子不符合
    const bargainTag = screen.getByText(/黄金坑探底/);
    fireEvent.click(bargainTag);

    expect(screen.getByText("银行")).toBeInTheDocument();
    expect(screen.queryByText("电子")).not.toBeInTheDocument();
  });

  it("opens drawer automatically when industry URL param is provided", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/leek-index?industry=电子"]}>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText(/散户博弈与韭菜指数详情/)).toBeInTheDocument();
  });

  it("renders mobile card stream when on narrow viewport", () => {
    vi.spyOn(mediaQueryHooks, "useMediaQuery").mockReturnValue(true);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("#2")).toBeInTheDocument();
    // 点击移动端卡片，抽屉弹出
    fireEvent.click(screen.getByText("#1"));
    expect(screen.getByText(/散户博弈与韭菜指数详情/)).toBeInTheDocument();
  });

  it("renders macro cockpit and filters by clicking risk tier", () => {
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    // 验证宏观驾驶舱关键元素
    expect(screen.getByText("31 行业风险梯队全景分布")).toBeInTheDocument();
    expect(screen.getByText("全市场博弈总敞口")).toBeInTheDocument();
    expect(screen.getByText("45.0")).toBeInTheDocument();
    expect(screen.getByText("全市场中位分 / 100")).toBeInTheDocument();

    // 点击梯队图例进行筛选（例如点击 🔥 极度接盘）
    const extremeTierBtns = screen.getAllByText("🔥 极度接盘");
    fireEvent.click(extremeTierBtns[0]);

    expect(screen.getByText("电子")).toBeInTheDocument();
    expect(screen.queryByText("银行")).not.toBeInTheDocument();
  });

  it("renders dual-axis history chart when industry drawer is opened", () => {
    vi.spyOn(sentimentHooks, "useIndustryLeekHistory").mockReturnValue({
      data: {
        industry_name: "电子",
        history: [
          {
            date: "2026-11-07",
            score: 82.0,
            risk_level: "extreme",
            sub_scores: { flow: 85, guba: 90, crowd: 70, trap: 80 },
            industry_change_pct: 1.2,
          },
          {
            date: "2026-11-08",
            score: 86.5,
            risk_level: "extreme",
            sub_scores: { flow: 90, guba: 100, crowd: 70, trap: 85 },
            industry_change_pct: 1.5,
          },
        ],
      },
      isLoading: false,
    } as unknown as ReturnType<typeof sentimentHooks.useIndustryLeekHistory>);

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/leek-index?industry=电子"]}>
          <LeekIndexPage />
        </MemoryRouter>
      </QueryClientProvider>
    );

    expect(screen.getByText("历史博弈走势双轴复盘 (近 30 个交易日)")).toBeInTheDocument();
    expect(screen.getByText(/近 2 日冲顶\(>75分\)频次/)).toBeInTheDocument();
    expect(screen.getByText("2 次")).toBeInTheDocument();
  });
});
