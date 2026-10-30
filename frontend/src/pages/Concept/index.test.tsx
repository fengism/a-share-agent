import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ApiError } from "../../api/client";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Concept from "./index";

const hooks = vi.hoisted(() => ({
  list: vi.fn(),
  constituents: vi.fn(),
  index: vi.fn(),
  hotConcept: vi.fn(),
  mainline: vi.fn(),
  indexSeries: vi.fn(),
}));

vi.mock("../../api/queryHooks/concept", () => ({
  useConceptList: (...args: unknown[]) => hooks.list(...args),
  useConceptConstituents: (...args: unknown[]) => hooks.constituents(...args),
  useConceptIndex: (...args: unknown[]) => hooks.index(...args),
  useConceptIndexSeries: (...args: unknown[]) => hooks.indexSeries(...args),
}));

vi.mock("../../api/queries", () => ({
  useThsHotConcept: () => hooks.hotConcept(),
  useMarketMainline: () => hooks.mainline(),
}));

// echarts 在 jsdom 无 canvas，用占位组件
vi.mock("echarts-for-react/lib/core", () => ({
  default: () => <div data-testid="compare-chart" />,
}));

vi.mock("../../api/queryHooks/watchlist", () => ({
  useWatchlist: () => ({ data: { items: [] } }),
  useAddWatchlistItem: () => ({ mutate: vi.fn() }),
  useDeleteWatchlistItem: () => ({ mutate: vi.fn() }),
}));

vi.mock("../../charts/KlineChart", () => ({
  default: ({ data }: { data: Array<{ date: string; close: number }> }) => (
    <div data-testid="kline">K线 {data.length} 根，收盘 {data.at(-1)?.close}</div>
  ),
}));

const CONCEPTS = [
  { name: "融资融券", stock_count: 3861 },
  { name: "固态电池", stock_count: 297 },
  { name: "宁德时代概念", stock_count: 199 },
  { name: "钠离子电池", stock_count: 92 },
];

const MAINLINE = {
  source: "财联社" as const,
  fetched_at: "2026-09-30T15:30:00",
  items: [
    {
      title: "算力主线",
      description: "",
      continued_days: 3,
      hot: 99,
      plates: [
        {
          code: "885001",
          name: "算力概念",
          reason: "算力租赁涨价",
          rise_count: 12,
          change_pct: 6.2,
          article_title: "",
          faucets: [{ code: "000002", name: "万科A", change_pct: 4.41, reason: "" }],
        },
      ],
    },
  ],
  style: null,
};

const HOT_CONCEPTS = [
  { rank: 1, code: "885001", name: "固态电池", change_pct: 5.21, hot_value: 99.2, hot_tag: "极高", tag: "固态电池" },
  { rank: 2, code: "885002", name: "机器人概念", change_pct: -1.3, hot_value: 88.1, hot_tag: "高", tag: "机器人" },
];

const CONSTITUENT_DATA = {
  concept: "融资融券",
  total: 3861,
  quote_source: "tdxhub",
  quote_covered: 1,
  related_concepts: [{ name: "固态电池", overlap: 12, ratio: 0.003 }],
  items: [{ code: "000002", name: "万科A", price: 4.26, change_pct: 1, amount: 1, quote_source: "tdxhub" }],
};

function setup() {
  hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
  hooks.constituents.mockReturnValue({
    data: CONSTITUENT_DATA,
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  });
  hooks.index.mockReturnValue({
    data: {
      concept: "融资融券",
      constituent_total: 3861,
      constituent_used: 800,
      truncated: true,
      items: [{ date: "2026-09-30", open: 1, high: 1, low: 1, close: 972.37, change_pct: 0.5, amount: 1, up_count: 433, down_count: 333, limit_up_count: 1, limit_down_count: 0, sample_count: 800 }],
    },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  });
  hooks.hotConcept.mockReturnValue({ data: HOT_CONCEPTS, isLoading: false });
  hooks.mainline.mockReturnValue({ data: MAINLINE, isLoading: false });
  hooks.indexSeries.mockReturnValue([]);
  return render(
    <MemoryRouter initialEntries={["/concept"]}>
      <Concept />
    </MemoryRouter>,
  );
}

describe("Concept page", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/concept");
    vi.clearAllMocks();
  });

  it("falls back to the largest concept when the URL carries none", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("融资融券 · 3861 只")).toBeInTheDocument());
  });

  it("renders the synthesized index KPI and the constituent table", async () => {
    setup();
    expect(await screen.findByTestId("kline")).toHaveTextContent("收盘 972.37");
    expect(screen.getByLabelText("合成指数点位")).toHaveTextContent("972.37");
    // KPI 条：全样本涨跌家数与样本口径
    expect(screen.getByText("涨 433")).toBeInTheDocument();
    expect(screen.getByText("跌 333")).toBeInTheDocument();
    expect(screen.getByText("800/800")).toBeInTheDocument();
    // 万科A 同时出现在右栏领涨榜与成分股表中
    expect(screen.getAllByText("万科A").length).toBeGreaterThan(0);
  });

  it("shows hot concepts as entry chips and switches on click", async () => {
    setup();
    const chip = await screen.findByRole("button", { name: /固态电池/ });
    fireEvent.click(chip);
    // 选择后写入"最近查看"，且概念标签切换为所选概念
    await waitFor(() => {
      const raw = window.localStorage.getItem("concept.recent_names");
      expect(raw ? (JSON.parse(raw) as unknown) : []).toContain("固态电池");
    });
    expect(
      screen.getByText((_, node) => node?.textContent === "固态电池 · 3861 只"),
    ).toBeInTheDocument();
  });

  /**
   * 回归：AutoComplete 的候选项必须跟着输入过滤。
   * 之前把搜索词只接在另一个输入框上，导致在这里输入"固态电池"，
   * 下拉仍显示按成分股数排序的前 10 个（第一条是"融资融券 3861 只"）。
   */
  it("filters the concept options by what the user typed", async () => {
    const { container } = setup();
    const combo = container.querySelector(".ant-select input") as HTMLInputElement;
    expect(combo).toBeTruthy();

    fireEvent.change(combo, { target: { value: "固态电池" } });

    // 输入过滤是纯前端计算（useConceptSearch），不依赖下拉是否在 jsdom 里展开
    await waitFor(() => {
      expect(screen.getByText("共 4 个概念 · 匹配 1")).toBeInTheDocument();
    });
  });

  it("shows the whole concept catalogue size when nothing is typed", async () => {
    setup();
    await waitFor(() => expect(screen.getByText("共 4 个概念")).toBeInTheDocument());
  });

  it("favorites the active concept and shows it in the watch row", async () => {
    setup();
    fireEvent.click(await screen.findByLabelText("收藏-融资融券"));
    await waitFor(() => {
      const stored = JSON.parse(window.localStorage.getItem("concept.favorite_names") || "[]") as string[];
      expect(stored).toContain("融资融券");
    });
    // 关注栏出现在热门栏之前，带星标
    expect(screen.getByText("关注")).toBeInTheDocument();
  });

  it("reads the index range from the URL", async () => {
    // 概念页直接读 window.location（不依赖路由状态），这里同步写入
    window.history.replaceState(null, "", "/concept?days=90");
    const daysCalls: number[] = [];
    hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
    hooks.constituents.mockReturnValue({
      data: CONSTITUENT_DATA,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    hooks.index.mockImplementation((_concept: unknown, days: number) => {
      daysCalls.push(days);
      return {
        data: { concept: "融资融券", constituent_total: 2, constituent_used: 2, truncated: false, items: [] },
        isLoading: false,
        error: null,
        refetch: vi.fn(),
      };
    });
    hooks.hotConcept.mockReturnValue({ data: [], isLoading: false });

    render(
      <MemoryRouter initialEntries={["/concept?days=90"]}>
        <Concept />
      </MemoryRouter>,
    );

    await waitFor(() => expect(daysCalls).toContain(90));
  });

  it("switches the catalogue to change-sorted listing on demand", async () => {
    const listCalls: Array<[number, string]> = [];
    window.history.replaceState(null, "", "/concept?concept=融资融券");
    hooks.list.mockImplementation((limit: number, order: string) => {
      listCalls.push([limit, order]);
      return { data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null };
    });
    hooks.constituents.mockReturnValue({
      data: CONSTITUENT_DATA,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    hooks.index.mockReturnValue({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() });
    hooks.hotConcept.mockReturnValue({ data: [], isLoading: false });
    hooks.mainline.mockReturnValue({ data: undefined, isLoading: false });

    render(
      <MemoryRouter initialEntries={["/concept?concept=融资融券"]}>
        <Concept />
      </MemoryRouter>,
    );

    // 默认按规模；切到按涨幅后列表请求应携带 order=change
    await waitFor(() => expect(listCalls.length).toBeGreaterThan(0));
    expect(listCalls.every(([, order]) => order === "size")).toBe(true);

    // 「按涨幅」同时也是成分股表排序选项，必须限定在选择卡的 meta 区域
    const meta = document.querySelector(".concept-search-meta")!;
    const item = Array.from(meta.querySelectorAll(".ant-segmented-item")).find(
      (el) => el.textContent === "按涨幅",
    );
    expect(item).toBeTruthy();
    fireEvent.click(item!);

    await waitFor(() => expect(listCalls.some(([, order]) => order === "change")).toBe(true));
  });

  it("shows today's mainline themes as chips and switches on click", async () => {
    setup();
    const chip = await screen.findByRole("button", { name: /算力概念/ });
    fireEvent.click(chip);
    await waitFor(() => {
      expect(
        screen.getByText((_, node) => node?.textContent === "算力概念 · 3861 只"),
      ).toBeInTheDocument();
    });
  });

  it("renders the compare view when the URL carries compare concepts", async () => {
    window.history.replaceState(null, "", "/concept?concept=融资融券&compare=固态电池");
    hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
    hooks.constituents.mockReturnValue({
      data: CONSTITUENT_DATA,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    hooks.index.mockReturnValue({
      data: { concept: "融资融券", constituent_total: 2, constituent_used: 2, truncated: false, items: [] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    });
    hooks.hotConcept.mockReturnValue({ data: [], isLoading: false });
    hooks.mainline.mockReturnValue({ data: undefined, isLoading: false });
    hooks.indexSeries.mockReturnValue([
      { data: { concept: "融资融券", constituent_total: 2, constituent_used: 2, truncated: false, items: [
        { date: "2026-09-26", open: 1, high: 1, low: 1, close: 1000, change_pct: 0, up_count: 1, down_count: 1, limit_up_count: 0, limit_down_count: 0, sample_count: 2, amount: 1 },
      ] }, isLoading: false },
      { data: { concept: "固态电池", constituent_total: 2, constituent_used: 2, truncated: false, items: [] }, isLoading: false },
    ]);

    render(
      <MemoryRouter initialEntries={["/concept?concept=融资融券&compare=固态电池"]}>
        <Concept />
      </MemoryRouter>,
    );

    // 默认视图是「走势」；点「对比」进入叠加图
    fireEvent.click(await screen.findByText("对比"));
    expect(await screen.findByTestId("compare-chart")).toBeInTheDocument();
    expect(screen.getByText("对比组合")).toBeInTheDocument();
  });

  it("shows a friendly not-found state with actions instead of error panels", async () => {
    hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
    hooks.constituents.mockReturnValue({
      data: undefined,
      isLoading: false,
      isFetching: false,
      error: new ApiError(404, "/concept/x/constituents", "未找到概念", { code: "concept.not_found" }),
      refetch: vi.fn(),
    });
    hooks.index.mockReturnValue({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() });
    hooks.hotConcept.mockReturnValue({ data: HOT_CONCEPTS, isLoading: false });

    render(
      <MemoryRouter initialEntries={["/concept?concept=不存在概念"]}>
        <Concept />
      </MemoryRouter>,
    );

    expect(await screen.findByText(/暂未收录或已更名/)).toBeInTheDocument();
    // 从热门概念一键脱困（热门榜第一名是固态电池）
    fireEvent.click(screen.getByRole("button", { name: "看热门概念" }));
    await waitFor(() => expect(screen.getByText(/「固态电池」暂未收录或已更名/)).toBeInTheDocument());
  });

  /**
   * 行情按需加载回归：首屏只应请求一小段代码，而不是全部成分股——
   * 上游按 80 只一批串行，全量请求在上游故障时会等几十秒。
   */
  it("requests only a first quote window on mount, then auto-extends", async () => {
    const calls: Array<string[] | undefined> = [];
    hooks.list.mockReturnValue({ data: { items: CONCEPTS }, isLoading: false, isFetching: false, error: null });
    hooks.constituents.mockImplementation((_concept: unknown, codes?: string[]) => {
      calls.push(codes);
      return {
        data: CONSTITUENT_DATA,
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: vi.fn(),
      };
    });
    hooks.index.mockReturnValue({ data: { items: [] }, isLoading: false, error: null, refetch: vi.fn() });
    hooks.hotConcept.mockReturnValue({ data: [], isLoading: false });

    render(
      <MemoryRouter initialEntries={["/concept"]}>
        <Concept />
      </MemoryRouter>,
    );

    await waitFor(() => expect(calls.some((codes) => Array.isArray(codes))).toBe(true));
    // 第一次是身份列表（不传行情代码），之后才按窗口补行情；首窗不超过 80 只
    const quoteCalls = calls.filter((codes): codes is string[] => Array.isArray(codes));
    expect(quoteCalls[0]).toEqual(["000002"]);
    expect(quoteCalls.every((codes) => codes.length <= 80)).toBe(true);
  });
});
