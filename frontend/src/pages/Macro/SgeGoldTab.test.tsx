import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import SgeGoldTab from "./SgeGoldTab";

const mocks = vi.hoisted(() => ({
  // 仅供既有的纯渲染用例替换 hook；其余用例走真实 hook + 真实请求
  hookOverride: { current: null as null | ((symbol: string) => unknown) },
  chart: vi.fn(() => <div data-testid="gold-kline" />),

  fetchMock: vi.fn(),
}));

vi.mock("../../api/queries", async () => {
  const actual = await vi.importActual<typeof import("../../api/queries")>("../../api/queries");
  return {
    ...actual,
    useSgeGoldHistory: (symbol = "Au99.99") =>
      mocks.hookOverride.current
        ? mocks.hookOverride.current(symbol)
        : actual.useSgeGoldHistory(symbol),
  };
});

// jsdom 没有 canvas 实现，echarts 重绘会抛错；此处只关心数据与交互锁定。
vi.mock("echarts-for-react/lib/core", () => ({
  default: mocks.chart,
}));

const history = [
  { date: "2026-08-01", open: 800, close: 805, low: 798, high: 808, change: null, change_pct: null },
  { date: "2026-09-02", open: 810.5, close: 812.3, low: 808, high: 815, change: 7.3, change_pct: 0.91 },
];

function buildResponseBody() {
  return {
    symbol: "Au99.99",
    name: "黄金 Au99.99",
    unit: "元/克",
    source: "上海黄金交易所",
    latest: history[1],
    history,
    updated_at: "2026-09-03T08:00:00+08:00",
    is_stale: false,
    is_delisted: false,
  };
}

function jsonResponse(overrides: Record<string, unknown> = {}) {
  return new Response(JSON.stringify({ ...buildResponseBody(), ...overrides }), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function renderTab() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return render(
    <QueryClientProvider client={client}>
      <SgeGoldTab />
    </QueryClientProvider>,
  );
}

describe("SgeGoldTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.hookOverride.current = null;
    vi.stubGlobal("fetch", mocks.fetchMock);
    mocks.fetchMock.mockResolvedValue(jsonResponse());
  });

  afterEach(() => {
    mocks.hookOverride.current = null;
    vi.unstubAllGlobals();
  });

  /** 既有用例不依赖真实请求，直接注入 hook 返回值。 */
  function stubHook(overrides: Record<string, unknown> = {}) {
    mocks.hookOverride.current = (current: string) => ({
      data: {
        symbol: current,
        name: current === "Ag(T+D)" ? "白银 Ag(T+D)" : "黄金 Au99.99",
        unit: current === "Ag(T+D)" ? "元/千克" : "元/克",
        source: "上海黄金交易所",
        latest: history[1],
        history,
        updated_at: "2026-09-03T08:00:00+08:00",
        is_stale: false,
        is_delisted: false,
        ...overrides,
      },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
  }

  it("renders latest quote and candlestick series", () => {
    stubHook();

    render(<SgeGoldTab />);

    expect(screen.getByText("812.30")).toBeInTheDocument();
    expect(screen.getByText("+0.91%")).toBeInTheDocument();
    expect(screen.getByText("808.00 / 815.00")).toBeInTheDocument();
    expect(screen.getByTestId("gold-kline")).toBeInTheDocument();
    expect(mocks.chart).toHaveBeenCalledWith(
      expect.objectContaining({
        option: expect.objectContaining({
          series: [expect.objectContaining({ type: "candlestick" })],
        }),
      }),
      expect.anything(),
    );

    const lastCall = (mocks.chart.mock.calls.at(-1) as unknown as [{ option?: { tooltip?: { formatter?: (params: unknown) => string } } } | undefined])?.[0];
    const tooltipFormatter = lastCall?.option?.tooltip?.formatter;
    expect(tooltipFormatter).toBeTypeOf("function");
    if (!tooltipFormatter) throw new Error("Expected tooltipFormatter to be defined");
    // ECharts category axis candlestick passes [categoryIndex, open, close, low, high]
    const tooltipText = tooltipFormatter([
      { axisValue: "2026-09-02", data: [1, 810.5, 812.3, 808, 815] },
    ]);
    expect(tooltipText).toContain("开盘：810.50");
    expect(tooltipText).toContain("收盘：812.30");
    expect(tooltipText).toContain("最低：808.00");
    expect(tooltipText).toContain("最高：815.00");
  });

  it("requests the newly selected SGE symbol", () => {
    const seen: string[] = [];
    mocks.hookOverride.current = (current: string) => {
      seen.push(current);
      return {
        data: {
          symbol: current,
          name: current === "Ag(T+D)" ? "白银 Ag(T+D)" : "黄金 Au99.99",
          unit: current === "Ag(T+D)" ? "元/千克" : "元/克",
          source: "上海黄金交易所",
          latest: history[1],
          history,
          updated_at: "2026-09-03T08:00:00+08:00",
          is_stale: false,
          is_delisted: false,
        },
        isLoading: false,
        isFetching: false,
        error: null,
        refetch: vi.fn(),
      };
    };

    render(<SgeGoldTab />);

    fireEvent.change(screen.getByLabelText("黄金品种"), { target: { value: "Ag(T+D)" } });

    expect(seen[seen.length - 1]).toBe("Ag(T+D)");
    expect(screen.getByText("白银 Ag(T+D)")).toBeInTheDocument();
  });

  it("renders the range switcher and cached history", async () => {
    renderTab();

    await waitFor(() => expect(screen.getByText("共 2 个交易日")).toBeInTheDocument());
    expect(screen.getByText("上海黄金交易所")).toBeInTheDocument();
    expect(screen.getByText("2026-09-02")).toBeInTheDocument();
  });

  it("flags a delisted contract instead of implying a live feed", async () => {
    mocks.fetchMock.mockResolvedValue(
      jsonResponse({ name: "黄金 Au(T+N2)", symbol: "Au(T+N2)", is_delisted: true }),
    );

    renderTab();

    await waitFor(() =>
      expect(screen.getByText(/黄金 Au\(T\+N2\) 已停止交易，仅供历史参考，不再更新行情/)).toBeInTheDocument(),
    );
    expect(screen.getByText("已停更")).toBeInTheDocument();
  });

  it("locks the symbol selector while a switch request is in flight", async () => {
    renderTab();

    const selector = screen.getByLabelText("黄金品种") as HTMLSelectElement;
    // 首次加载期间同样锁定，避免用户连点打满上金所配额
    await waitFor(() => expect(selector).toBeDisabled());
    await waitFor(() => expect(selector).toBeEnabled());
  });

  it("keeps the previous chart visible and marks switching when the symbol changes", async () => {
    let release!: () => void;
    const gate = new Promise<void>((resolve) => {
      release = resolve;
    });
    mocks.fetchMock.mockResolvedValueOnce(jsonResponse());
    renderTab();

    const selector = screen.getByLabelText("黄金品种") as HTMLSelectElement;
    await waitFor(() => expect(screen.getByText("共 2 个交易日")).toBeInTheDocument());

    // 第二次请求挂起，模拟切换品种时的加载窗口
    mocks.fetchMock.mockImplementationOnce(async () => {
      await gate;
      return jsonResponse();
    });
    fireEvent.change(selector, { target: { value: "Ag99.99" } });

    await waitFor(() => expect(selector).toBeDisabled());
    expect(screen.getByText("正在切换品种…")).toBeInTheDocument();
    // 切换期间保留上一品种数据，避免图表闪空
    expect(screen.getByText("共 2 个交易日")).toBeInTheDocument();

    release();
    await waitFor(() => expect(selector).toBeEnabled());
  });
});