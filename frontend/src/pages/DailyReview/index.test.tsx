import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { streamDailyReview } from "../../api/sse";
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
  warnings: [] as string[],
  notes: [] as string[],
  sentiment_cycle: undefined as
    | undefined
    | {
        stage: "冰点" | "修复回暖" | "主升共振" | "高位分化" | "退潮杀跌";
        ladder_health?: string;
        evidence: string[];
      },
  scenario_plans: undefined as
    | undefined
    | Array<{
        name: "超预期" | "符合预期" | "低于预期";
        trigger?: string;
        playbook?: string;
        watch_levels: string[];
      }>,
  next_day_watchlist: undefined as
    | undefined
    | Array<{
        name: string;
        role: "总龙头" | "连板最高板" | "中军容量票" | "负反馈票";
        reason?: string;
        trigger?: string;
      }>,
  key_levels: undefined as undefined | string[],
  previous_review_check: undefined as
    | undefined
    | {
        review_date: string;
        verified_date: string;
        indices?: Array<{ code?: string; name: string; previous_change_pct?: number | null; change_pct?: number | null }>;
        watchlist?: Array<{
          name: string;
          code?: string;
          role?: string;
          change_pct?: number | null;
          hit: boolean;
          limit_up: boolean;
          missing: boolean;
        }>;
        hit_count: number;
        checked_count: number;
        previous_stage?: string;
        limit_up_count?: number | null;
        previous_limit_up_count?: number | null;
        limit_up_delta?: number | null;
        note?: string;
      },
  cycle_trend: undefined as
    | undefined
    | {
        points?: Array<{
          date: string;
          stage?: string;
          limit_up_count?: number | null;
          break_rate?: number | null;
          index_change_pct?: number | null;
          next_index_change_pct?: number | null;
          stage_transition?: string;
        }>;
        stage_stats?: Array<{
          stage: string;
          occurrences: number;
          next_day_up_ratio?: number | null;
          avg_next_day_index_change_pct?: number | null;
        }>;
        note?: string;
      },
  data_snapshot: {
    source_status: undefined as
      | undefined
      | Record<string, { status: "complete" | "partial" | "unavailable"; data_date?: string; error?: string }>,
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

vi.mock("../../api/sse", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../api/sse")>();
  return { ...actual, streamDailyReview: vi.fn() };
});

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

  /** 打开「导出」下拉并点选指定项 */
  async function clickExportItem(label: string | RegExp) {
    fireEvent.click(screen.getByRole("button", { name: /导出/ }));
    const matcher = typeof label === "string" ? new RegExp(label) : label;
    const item = await screen.findByRole("menuitem", { name: matcher });
    fireEvent.click(item);
  }

  /** 章节默认折叠，断言内容前先按标题展开 */
  function expandSection(title: string | RegExp) {
    // 目录 chips 与折叠头重名，用 aria-expanded 锁定折叠触发器
    // （折叠头可访问名还包含右侧摘要，如「政策与事件传导 3 条」）
    const matcher = typeof title === "string" ? new RegExp(title) : title;
    const trigger = screen
      .getAllByRole("button", { name: matcher })
      .find((element) => element.hasAttribute("aria-expanded"));
    if (!trigger) throw new Error(`未找到章节折叠按钮：${String(title)}`);
    if (trigger.getAttribute("aria-expanded") !== "true") {
      fireEvent.click(trigger);
    }
  }

  it("renders daily review details with export actions and snapshot metrics", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: /每日复盘/, level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /重新生成|生成复盘/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /导出/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "更多操作" })).toBeInTheDocument();

    expect(screen.getByText("A股市场每日复盘 - 2026-08-25")).toBeInTheDocument();
    expect(screen.getByText(/今日A股主要指数多数收涨/)).toBeInTheDocument();
    // Hero 区展示核心结论指标（涨停家数 / 炸板率 / 指数涨跌 / 情绪阶段）
    expect(screen.getByText("涨停家数")).toBeInTheDocument();
    expect(screen.getByText("炸板率")).toBeInTheDocument();
    expandSection(/政策与事件传导/);
    // 折叠头已承载分区标题，卡片标题不再重复渲染
    expect(screen.getByText(/流动性释放/)).toBeInTheDocument();
    expect(screen.getByText(/银行板块放量领涨/)).toBeInTheDocument();
    expect(screen.getByText("流动性释放 → 风险偏好改善 → 金融权重获得增量资金关注")).toBeInTheDocument();
    expect(screen.getByText(/银行与券商成交额放大/)).toBeInTheDocument();
    expect(screen.getByText("事后验证")).toBeInTheDocument();
    expect(screen.getByText(/仅用于事后验证，不作为当日交易依据/)).toBeInTheDocument();
  });

  it("supports copying review to clipboard and exporting via dropdown", async () => {
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

    await clickExportItem("复制复盘内容");
    expect(writeTextSpy).toHaveBeenCalledWith(expect.stringContaining("A股市场每日复盘 - 2026-08-25"));

    // Open export dropdown and select Markdown
    await clickExportItem("导出为 Markdown");
    expect(window.URL.createObjectURL).toHaveBeenCalled();
    expect(clickSpy).toHaveBeenCalled();
    clickSpy.mockRestore();
  });

  it("renders auxiliary data notes without marking the review degraded", () => {
    mockReview.notes = ["macro_analysis：数据部分可用"];
    renderPage();

    expect(screen.getByText("部分辅助数据缺失（不影响复盘结论）")).toBeInTheDocument();
    expect(screen.getByText("macro_analysis：数据部分可用")).toBeInTheDocument();
    expect(screen.queryByText("复盘数据或生成过程不完整")).not.toBeInTheDocument();

    mockReview.notes = [];
  });

  it("exports source status and warnings into the markdown", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextSpy } });
    mockReview.warnings = ["核心复盘数据缺失：market_volume"];
    mockReview.data_snapshot.source_status = {
      macro_analysis: { status: "partial", data_date: "2026-08-25", error: "2 条宏观事件待后台解读" },
    };
    renderPage();

    await clickExportItem("复制复盘内容");

    const exported = writeTextSpy.mock.calls[0][0] as string;
    expect(exported).toContain("## 数据核验警告");
    expect(exported).toContain("⚠️ 核心复盘数据缺失：market_volume");
    expect(exported).toContain("## 复盘数据状态");
    expect(exported).toContain("macro_analysis：部分（数据日期 2026-08-25） — 2 条宏观事件待后台解读");

    mockReview.warnings = [];
    mockReview.data_snapshot.source_status = undefined;
  });

  it("renders deep review cards and exports them to markdown", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextSpy } });
    mockReview.sentiment_cycle = {
      stage: "修复回暖",
      ladder_health: "二板及以上 12 家，梯队无断层",
      evidence: ["空间板 6 板（甲）", "炸板率 16.7%"],
    };
    mockReview.scenario_plans = [
      { name: "超预期", trigger: "放量高开", playbook: "加仓领涨主线", watch_levels: ["成交额 1.5 万亿"] },
      { name: "符合预期", trigger: "平开震荡", playbook: "持股待涨", watch_levels: [] },
      { name: "低于预期", trigger: "低开走弱", playbook: "降仓防守", watch_levels: [] },
    ];
    mockReview.next_day_watchlist = [
      { name: "甲", role: "连板最高板", reason: "当日空间板（6 板）", trigger: "竞价能否维持强势" },
    ];
    mockReview.key_levels = ["上证 3250 支撑；压力 3350"];
    renderPage();

    // 章节标题始终可见（目录与折叠头），内容需展开后断言
    expect(screen.getAllByRole("button", { name: /情绪周期定位/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /明日三情景预案/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /次日观察锚点/ }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /关键点位与量能阈值/ }).length).toBeGreaterThan(0);

    expandSection(/情绪周期定位/);
    // Hero 的情绪阶段徽标与章节内容都会展示阶段名
    expect(screen.getAllByText("修复回暖").length).toBeGreaterThan(0);

    await clickExportItem("复制复盘内容");

    const exported = writeTextSpy.mock.calls[0][0] as string;
    expect(exported).toContain("## 情绪周期定位：修复回暖");
    expect(exported).toContain("## 明日三情景预案");
    expect(exported).toContain("**超预期**：触发 放量高开；应对 加仓领涨主线");
    expect(exported).toContain("## 次日观察锚点");
    expect(exported).toContain("**甲**（连板最高板）");
    expect(exported).toContain("## 关键点位与量能阈值");

    mockReview.sentiment_cycle = undefined;
    mockReview.scenario_plans = undefined;
    mockReview.next_day_watchlist = undefined;
    mockReview.key_levels = undefined;
  });

  it("renders the previous review self-check and cycle trend", async () => {
    const writeTextSpy = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText: writeTextSpy } });
    mockReview.previous_review_check = {
      review_date: "2026-08-24",
      verified_date: "2026-08-25",
      indices: [{ name: "上证指数", previous_change_pct: 0.8, change_pct: -0.42 }],
      watchlist: [
        { name: "甲", code: "600000", role: "连板最高板", change_pct: 10.0, hit: true, limit_up: true, missing: false },
        { name: "乙", code: "600001", role: "中军容量票", change_pct: -3.2, hit: false, limit_up: false, missing: false },
      ],
      hit_count: 1,
      checked_count: 2,
      previous_stage: "修复回暖",
      limit_up_count: 42,
      previous_limit_up_count: 55,
      limit_up_delta: -13,
      note: "空间板未能延续，情绪高位分化。",
    };
    mockReview.cycle_trend = {
      points: [
        { date: "2026-08-22", stage: "冰点", limit_up_count: 21, break_rate: 0.42, index_change_pct: -1.2, stage_transition: "降级" },
        { date: "2026-08-25", stage: "修复回暖", limit_up_count: 42, break_rate: 0.167, index_change_pct: 0.8, next_index_change_pct: -0.42 },
      ],
      stage_stats: [{ stage: "修复回暖", occurrences: 2, next_day_up_ratio: 0.5, avg_next_day_index_change_pct: -0.42 }],
      note: "近 20 个交易日样本。",
    };
    renderPage();

    expandSection(/昨日复盘自检/);
    expect(screen.getByText("观察锚点逐项对照")).toBeInTheDocument();
    expect(screen.getByText("命中 1/2")).toBeInTheDocument();
    expandSection(/情绪周期历史趋势/);
    expect(screen.getByRole("list", { name: "情绪周期时间轴" })).toBeInTheDocument();
    expect(screen.getByText(/出现 2 次/)).toBeInTheDocument();
    expect(screen.getByText(/次日指数上涨/)).toBeInTheDocument();

    await clickExportItem("复制复盘内容");

    const exported = writeTextSpy.mock.calls[0][0] as string;
    expect(exported).toContain("## 上一交易日复盘自检（2026-08-24 → 2026-08-25）");
    expect(exported).toContain("- 观察标的命中率：1/2");
    expect(exported).toContain("- 甲：次日 +10.00%，次日涨停（命中）");
    expect(exported).toContain("## 情绪周期历史趋势");
    expect(exported).toContain("- 阶段统计：修复回暖 出现 2 次");

    mockReview.previous_review_check = undefined;
    mockReview.cycle_trend = undefined;
  });

  it("shows backend stage progress while generating", async () => {
    vi.mocked(streamDailyReview).mockImplementation((_request, onProgress) => {
      onProgress({ type: "stage_started", stage: "collect", message: "正在采集行情、资金、新闻与宏观数据…" });
      return {
        promise: new Promise(() => {}),
        started: Promise.resolve({ job_id: 1, dedupe_key: "2026-08-25", status: "running" }),
        cancel: vi.fn().mockResolvedValue("cancelled"),
        detach: vi.fn(),
      } as never;
    });
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /重新生成|生成复盘/ }));
    fireEvent.click(await screen.findByRole("menuitem", { name: /重新生成复盘|生成复盘/ }));

    expect(await screen.findByText("正在采集行情、资金、新闻与宏观数据…")).toBeInTheDocument();
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
