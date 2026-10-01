import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DailyReviewPage from "./index";

const mockReview = {
  date: "2026-08-25",
  title: "A股市场每日复盘 - 2026-08-25",
  market_summary: "今日A股主要指数多数收涨，两市成交额突破1.2万亿元，机器人与算力领涨。",
  quality_status: "complete",
  generation_status: "llm",
  session_status: "normal",
  effective_date: "2026-08-25",
  requested_date: "2026-08-25",
  generated_at: "2026-08-25 16:30:00",
  opportunities: ["机器人产业利好持续释放", "算力硬件需求增加"],
  risk_alerts: ["高位消费股获利了结风险"],
  strategy_notes: ["控制半仓，逢低布局低估核心资产"],
  news_policy_review: {
    title: "新闻政策与影响传导",
    summary: "政策催化需要盘面确认，不能把新闻直接等同于交易结论。",
    bullets: ["央行宣布降准，观察银行与券商成交额是否放大。"],
  },
  event_impacts: [{
    event_title: "央行宣布降准",
    event_type: "policy",
    direction: "positive",
    timing: "on_date",
    horizon: "short_term",
    affected_sectors: ["银行", "券商"],
    transmission_chain: "流动性释放 → 风险偏好改善 → 金融权重获得增量资金关注",
    evidence: "中国人民银行 2026-08-25：央行宣布降准",
    market_confirmation: "银行板块放量领涨，获得初步盘面确认。",
    confirmation_signals: ["银行与券商成交额放大"],
    invalidation_conditions: ["金融权重高开低走"],
  }, {
    event_title: "次日政策细则落地",
    event_type: "policy",
    direction: "mixed",
    timing: "after",
    horizon: "short_term",
    affected_sectors: ["新能源车"],
    transmission_chain: "细则落地 → 核对补贴力度 → 验证汽车板块持续性",
    evidence: "国务院 2026-08-26：次日政策细则落地",
    confirmation_signals: ["汽车板块次日放量"],
    invalidation_conditions: ["板块冲高回落"],
  }],
  warnings: [],
  data_snapshot: {
    indices: [{ code: "000001", name: "上证指数", change_pct: 1.2 }],
    hot_stocks: [{ code: "600519", name: "贵州茅台", change_pct: 1.5 }],
    hot_concepts: [{ code: "BK0800", name: "机器人概念", change_pct: 4.2 }],
    hot_industries: [{ code: "BK0400", name: "机械设备", change_pct: 3.1 }],
    dragon_tiger: [{ code: "002230", name: "科大讯飞" }],
    top_sectors: [{ name: "机器人", change_pct: 4.28 }],
    bottom_sectors: [{ name: "煤炭", change_pct: -2.14 }],
    market_statistics: {
      up_count: 3200,
      down_count: 1600,
      flat_count: 100,
      limit_up_count: 65,
      limit_down_count: 5,
    },
    market_volume: {
      amount: 1_200_000_000_000,
    },
    policy_news: [{ title: "央行宣布降准", event_type: "policy", direction: "positive" }],
  },
  llm_review: "## 市场综述\n\n今日三大指数集体走强，成交量显著放大。\n\n## 行业表现\n\n科技板块全线爆发。",
};

const mockHistoryPages = {
  pages: [
    [
      { date: "2026-08-25", title: "A股每日复盘 08-25", can_delete: true },
      { date: "2026-08-24", title: "A股每日复盘 08-24", can_delete: true },
      { date: "2026-08-23", title: "A股每日复盘 08-23", can_delete: false },
      { date: "2026-08-22", title: "A股每日复盘 08-22", can_delete: false },
    ],
  ],
};

vi.mock("../../api/queries", () => ({
  useDailyReview: () => ({
    data: mockReview,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
  }),
  useInfiniteDailyReviewHistory: () => ({
    data: mockHistoryPages,
    isLoading: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    hasNextPage: false,
    fetchNextPage: vi.fn(),
    isFetchingNextPage: false,
  }),
  useDeleteDailyReview: () => ({
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  downloadDailyReviewPdf: vi.fn(),
}));

vi.mock("../../hooks/useWorkflowPush", () => ({
  useWorkflowPush: () => ({
    push: vi.fn(),
    isPushing: false,
  }),
}));

describe("DailyReviewPage", () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
  });

  const renderPage = () =>
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/daily-review?date=2026-08-25"]}>
          <DailyReviewPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

  it("renders daily review details with export actions and snapshot metrics", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: /每日复盘/, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "生成复盘" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /导出/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /复制/ })).toBeInTheDocument();

    expect(screen.getByText("A股市场每日复盘 - 2026-08-25")).toBeInTheDocument();
    expect(screen.getByText(/今日A股主要指数多数收涨/)).toBeInTheDocument();
    expect(screen.getByText(/指数 1/)).toBeInTheDocument();
    expect(screen.getByText(/热股 1/)).toBeInTheDocument();
    expect(screen.getByText(/概念 1/)).toBeInTheDocument();
    expect(screen.getAllByText("新闻政策与影响传导").length).toBeGreaterThan(0);
    expect(screen.getByText(/银行板块放量领涨/)).toBeInTheDocument();
    expect(screen.getByText("流动性释放 → 风险偏好改善 → 金融权重获得增量资金关注")).toBeInTheDocument();
    expect(screen.getByText(/银行与券商成交额放大/)).toBeInTheDocument();
    expect(screen.getByText("事后验证")).toBeInTheDocument();
    expect(screen.getByText(/仅用于事后验证，不作为当日交易依据/)).toBeInTheDocument();
  });

  it("supports copying review to clipboard and exporting via dropdown", () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextSpy,
      },
    });
    window.URL.createObjectURL = vi.fn(() => "blob:mock-url");
    window.URL.revokeObjectURL = vi.fn();
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    renderPage();

    const copyBtn = screen.getByRole("button", { name: /复制/ });
    fireEvent.click(copyBtn);
    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("A股市场每日复盘 - 2026-08-25"));

    // Open export dropdown and select Markdown
    const exportBtn = screen.getByRole("button", { name: /导出/ });
    fireEvent.click(exportBtn);

    const exportMdItem = screen.getByText("导出为 Markdown (.md)");
    fireEvent.click(exportMdItem);
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("supports searching and filtering history items", () => {
    renderPage();

    const searchInput = screen.getByPlaceholderText("搜索历史复盘...");
    expect(searchInput).toBeInTheDocument();

    expect(screen.getByText("A股每日复盘 08-25")).toBeInTheDocument();
    expect(screen.getByText("A股每日复盘 08-22")).toBeInTheDocument();

    fireEvent.change(searchInput, { target: { value: "08-22" } });
    expect(screen.getByText("A股每日复盘 08-22")).toBeInTheDocument();
    expect(screen.queryByText("A股每日复盘 08-25")).not.toBeInTheDocument();
  });
});
