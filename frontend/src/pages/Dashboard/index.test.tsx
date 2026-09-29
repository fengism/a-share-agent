import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import Dashboard from "./index";
import type { MarketMainline } from "../../types/stock/market";

const mocks = vi.hoisted(() => ({
  intraday: vi.fn(),
  windStocks: vi.fn(),
  mainlineQuery: {
    data: {
      source: "财联社",
      fetched_at: "2026-08-21T10:30:00+08:00",
      style: {
        title: "高位科技抱团逐步瓦解，市场风格或转向均衡轮动",
        interpret: "资金配置重心逐步向外扩散。",
        indexes: [
          {
            code: "000001",
            name: "上证指数",
            change_30d: -2.28,
            stocks: [
              { code: "603580", name: "艾艾精工", change_30d: 163.3 },
            ],
          },
        ],
      },
      items: [
        {
          title: "创新药",
          description: "龙头药明康德公告全面上调全年业绩指引。",
          continued_days: 4,
          hot: 4,
          plates: [
            {
              code: "cls80044",
              name: "创新药",
              reason: "药明康德公告业绩指引上调。",
              rise_count: 4,
              change_pct: -4.05,
              article_title: "市场再现缩量修复",
              faucets: [
                { code: "600721", name: "百花医药", change_pct: -3, reason: "16天涨超90%" },
              ],
            },
          ],
        },
      ],
    } as MarketMainline | null,
    isLoading: false,
    isFetching: false,
    error: null as unknown,
    refetch: vi.fn(),
  },
}));

function resetMainlineQuery() {
  mocks.mainlineQuery.data = mainlineSnapshot();
  mocks.mainlineQuery.isLoading = false;
  mocks.mainlineQuery.isFetching = false;
  mocks.mainlineQuery.error = null;
  mocks.mainlineQuery.refetch.mockReset();
  mocks.windStocks.mockImplementation((plateCode: string) => ({
    data: {
      source: "财联社",
      fetched_at: "2026-08-21T10:30:00+08:00",
      plate_code: plateCode,
      items: plateCode === "cls82580"
        ? [{ code: "300153", name: "科泰电源", price: 28.5, change_pct: 12.3, limit_up_days: 1 }]
        : [{ code: "600276", name: "恒瑞医药", price: 62.18, change_pct: 3.21, limit_up_days: 0 }],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }));
}

function mainlineSnapshot(): MarketMainline {
  return {
    source: "财联社",
    fetched_at: "2026-08-21T10:30:00+08:00",
    style: {
      title: "高位科技抱团逐步瓦解，市场风格或转向均衡轮动",
      interpret: "资金配置重心逐步向外扩散。",
      indexes: [
        {
          code: "000001",
          name: "上证指数",
          change_30d: -2.28,
          stocks: [
            { code: "603580", name: "艾艾精工", change_30d: 163.3 },
          ],
        },
      ],
    },
    items: [
      {
        title: "创新药",
        description: "龙头药明康德公告全面上调全年业绩指引。",
        continued_days: 4,
        hot: 4,
        plates: [
          {
            code: "cls80044",
            name: "创新药",
            reason: "药明康德公告业绩指引上调。",
            rise_count: 4,
            change_pct: -4.05,
            article_title: "市场再现缩量修复",
            faucets: [
              { code: "600721", name: "百花医药", change_pct: -3, reason: "16天涨超90%" },
            ],
          },
        ],
      },
    ],
  };
}

vi.mock("../../components/MarketOverviewBoard", () => ({
  default: ({
    onNavigate,
    showRankings = true,
  }: {
    onNavigate: (tab: string) => void;
    showRankings?: boolean;
  }) => (
    <section aria-label="市场看板">
      <button type="button" onClick={() => onNavigate("emotion")}>查看市场情绪详情</button>
      {showRankings ? <><span>行业强弱</span><span>热门概念</span></> : null}
    </section>
  ),
}));

vi.mock("../../api/queries", () => ({
  useMarketIndices: () => ({
    data: { source: "腾讯", indices: [
      { code: "000001", name: "上证指数", price: 3200, change_pct: 0.5, amount: 100000000 },
      { code: "399001", name: "深证成指", price: 11000, change_pct: -0.2, amount: 200000000 },
    ] },
    isLoading: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketIndexIntraday: (symbol: string) => {
    mocks.intraday(symbol);
    return {
      data: { code: symbol, source: "sina_direct", prev_close: null, items: [{ time: "09:30:00", price: 3200, avg_price: 3199, volume: 10 }] },
      isLoading: false,
      error: null,
      refetch: vi.fn(),
    };
  },
  useMarketMainline: () => mocks.mainlineQuery,
  useMarketWind: () => ({
    data: {
      source: "财联社",
      fetched_at: "2026-08-21T10:30:00+08:00",
      items: [
        { plate_code: "cls80044", plate_name: "创新药", catalyst: "政策与业绩共振" },
        { plate_code: "cls82580", plate_name: "IDC电源", catalyst: "AI服务器电源需求增长" },
      ],
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useMarketWindStocks: (plateCode: string) => mocks.windStocks(plateCode),
  useThsHotRank: () => ({
    data: [],
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useThsHotConcept: () => ({
    data: [],
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
  useThsHotIndustry: () => ({
    data: [],
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: vi.fn(),
  }),
}));

vi.mock("../../charts/IntradayChart", () => ({ default: () => <div>首页指数分时图</div> }));

vi.mock("./WatchlistPanel", () => ({
  default: () => <div data-testid="watchlist-panel">我的自选</div>,
}));

describe("Dashboard", () => {
  beforeEach(() => {
    resetMainlineQuery();
  });

  it("keeps market wind and mainline in the middle while hot rank and watchlist stay right", () => {
    const { container } = render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(container.querySelector(".dashboard-page")).toHaveStyle({
      width: "100%",
      maxWidth: "none",
    });
    const layout = container.querySelector(".dashboard-layout");
    const middle = screen.getByRole("region", { name: "首页中间内容" });
    const rail = screen.getByRole("complementary", { name: "首页热榜与自选栏" });
    expect(layout?.firstElementChild).toBe(middle);
    expect(layout?.lastElementChild).toBe(rail);
    expect(within(middle).getByRole("region", { name: "首页市场看板" })).toBeInTheDocument();
    expect(within(middle).getByRole("region", { name: "市场风向" })).toBeInTheDocument();
    expect(within(middle).getByRole("region", { name: "今日主线" })).toBeInTheDocument();
    expect(within(middle).getByText("政策与业绩共振")).toBeInTheDocument();
    expect(within(rail).queryByRole("region", { name: "市场风向" })).not.toBeInTheDocument();
    const hotRank = within(rail).getByRole("region", { name: "热榜" });
    const watchlist = within(rail).getByTestId("watchlist-panel");
    expect(hotRank).toBeInTheDocument();
    expect(watchlist).toBeInTheDocument();
    expect(rail.firstElementChild).toBe(hotRank);
    expect(rail.lastElementChild).toBe(watchlist);
    expect(within(rail).getByText("热股榜")).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "指数分时" })).not.toBeInTheDocument();
    expect(screen.queryByText("首页指数分时图")).not.toBeInTheDocument();
    expect(mocks.intraday).not.toHaveBeenCalled();
    expect(screen.queryByText(/当前查看/)).not.toBeInTheDocument();
    expect(screen.queryByText("市场行情")).not.toBeInTheDocument();
    expect(screen.queryByText("对话")).not.toBeInTheDocument();
    expect(screen.queryByText("AI 分析")).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "市场总览" })).toBeInTheDocument();
    expect(screen.queryByText("行业强弱")).not.toBeInTheDocument();
    expect(screen.queryByText("热门概念")).not.toBeInTheDocument();
  });

  it("switches the displayed leader stocks when a market wind plate is clicked", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    const section = screen.getByRole("region", { name: "市场风向" });
    expect(await within(section).findByText("恒瑞医药")).toBeInTheDocument();
    expect(within(section).getByRole("button", { name: "选择风口 创新药" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );

    fireEvent.click(within(section).getByRole("button", { name: "选择风口 IDC电源" }));

    expect(await within(section).findByText("科泰电源")).toBeInTheDocument();
    expect(mocks.windStocks).toHaveBeenCalledWith("cls82580");
    expect(within(section).getByRole("button", { name: "选择风口 IDC电源" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("renders today's mainline chances with plates and faucet stocks", () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    const section = screen.getByRole("region", { name: "今日主线" });
    expect(within(section).getAllByText("创新药").length).toBeGreaterThan(0);
    expect(within(section).getByText("持续 4 天")).toBeInTheDocument();
    expect(within(section).getByText("热度 4")).toBeInTheDocument();
    expect(within(section).getByText(/药明康德公告全面上调/)).toBeInTheDocument();
    expect(within(section).getByText("4 家上涨")).toBeInTheDocument();

    expect(within(section).getByText("主线龙头股（1）")).toBeInTheDocument();
    const faucetTable = within(section).getAllByRole("table")[0];
    expect(within(faucetTable).getByRole("link", { name: /百花医药/ })).toHaveAttribute(
      "href",
      expect.stringContaining("600721"),
    );
    expect(within(faucetTable).getByText("16天涨超90%")).toBeInTheDocument();

    expect(within(section).getByText("风格判断")).toBeInTheDocument();
    expect(within(section).getByText("高位科技抱团逐步瓦解，市场风格或转向均衡轮动")).toBeInTheDocument();
    expect(within(section).getByText("指数表现")).toBeInTheDocument();
    expect(within(section).getByText("代表个股")).toBeInTheDocument();
    // 指数名称出现在"指数表现"表格行与"代表个股"的所属指数列各一次
    expect(within(section).getAllByText("上证指数")).toHaveLength(2);
    expect(within(section).getByText("1 条主线")).toBeInTheDocument();
    expect(within(section).getByRole("status")).toBeInTheDocument();
    fireEvent.click(within(section).getByRole("button", { name: "刷新今日主线" }));
    expect(mocks.mainlineQuery.refetch).toHaveBeenCalledOnce();
    expect(within(section).getAllByRole("link", { name: /艾艾精工/ })[0]).toHaveAttribute(
      "href",
      expect.stringContaining("603580"),
    );
  });

  it("shows the mainline error state without affecting indices or watchlist", () => {
    mocks.mainlineQuery.data = null;
    mocks.mainlineQuery.error = new Error("upstream failed");

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    const section = screen.getByRole("region", { name: "今日主线" });
    expect(within(section).getByText("今日主线加载失败")).toBeInTheDocument();
    expect(within(section).getByRole("button", { name: /重\s*试/ })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "指数分时" })).not.toBeInTheDocument();
  });

  it("shows the mainline empty state when no chances are available", () => {
    mocks.mainlineQuery.data = {
      source: "财联社",
      fetched_at: "2026-08-21T10:30:00+08:00",
      style: null,
      items: [],
    };

    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    const section = screen.getByRole("region", { name: "今日主线" });
    expect(within(section).getByText("暂无今日主线数据")).toBeInTheDocument();
    expect(within(section).queryByText("风格判断")).not.toBeInTheDocument();
  });

  it("renders new shortcuts and supports faucet stock quick actions and csv export", () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>,
    );

    expect(screen.getByRole("button", { name: /国家队监测/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /每日复盘/ })).toBeInTheDocument();

    const section = screen.getByRole("region", { name: "今日主线" });
    expect(within(section).getByRole("button", { name: /导出 CSV/ })).toBeInTheDocument();
    expect(within(section).getAllByRole("link", { name: "研报" })[0]).toHaveAttribute("href", "/analysis?code=600721");
    expect(within(section).getAllByRole("link", { name: "回测" })[0]).toHaveAttribute("href", "/quant?codes=600721");
  });
});
