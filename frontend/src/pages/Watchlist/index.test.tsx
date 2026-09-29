import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import WatchlistPage from ".";
import type { WatchlistItem } from "../../types/watchlist";

const mocks = vi.hoisted(() => ({
  add: vi.fn(),
  remove: vi.fn(),
  addAlert: vi.fn(),
  deleteAlert: vi.fn(),
  refetch: vi.fn(),
}));

const items: WatchlistItem[] = [
  {
    id: 1,
    stock_code: "600519",
    stock_name: "贵州茅台",
    note: "核心观察",
    created_at: "2026-08-20T10:00:00",
    current_price: 1518.2,
    change_pct: 1.26,
    open_price: 1502,
    high_price: 1522.8,
    low_price: 1498.5,
    previous_close: 1499.31,
    volume: 2_300_000,
    amount: 3_480_000_000,
    turnover_pct: 0.19,
    pe_ttm: 23.45,
    market_cap: 1_905_000_000_000,
    quote_source: "tencent",
    concepts: [
      { code: "BK0896", name: "白酒概念" },
      { code: "BK1234", name: "茅指数" },
    ],
    alerts: [],
  },
  {
    id: 2,
    stock_code: "000858",
    stock_name: "五粮液",
    note: "",
    created_at: "2026-08-21T10:00:00",
    current_price: 121.56,
    change_pct: -0.45,
    open_price: 122.1,
    high_price: 123,
    low_price: 120.8,
    previous_close: 122.11,
    volume: 6_100_000,
    amount: 742_000_000,
    turnover_pct: 0.32,
    pe_ttm: 18.23,
    market_cap: 471_800_000_000,
    quote_source: "tencent",
    concepts: [{ code: "BK0896", name: "白酒概念" }],
    alerts: [],
  },
  {
    id: 3,
    stock_code: "601991",
    stock_name: "大唐发电",
    note: "",
    created_at: "2026-08-22T10:00:00",
    current_price: 3.25,
    change_pct: 0,
    open_price: 3.25,
    high_price: 3.28,
    low_price: 3.21,
    previous_close: 3.25,
    volume: 18_000_000,
    amount: 58_500_000,
    turnover_pct: 0.42,
    pe_ttm: 12.8,
    market_cap: 60_100_000_000,
    quote_source: "tencent",
    concepts: [],
    alerts: [],
  },
];

vi.mock("../../api/queries", () => ({
  useWatchlist: () => ({
    data: {
      items,
      source: "tencent",
      quoted_at: "2026-08-30T10:30:00",
    },
    isLoading: false,
    isFetching: false,
    error: null,
    refetch: mocks.refetch,
  }),
  useAddWatchlistItem: () => ({ mutateAsync: mocks.add, isPending: false }),
  useDeleteWatchlistItem: () => ({ mutateAsync: mocks.remove, isPending: false }),
  useAddWatchlistAlert: () => ({ mutateAsync: mocks.addAlert, isPending: false }),
  useDeleteWatchlistAlert: () => ({ mutateAsync: mocks.deleteAlert, isPending: false }),
}));

vi.mock("../../hooks/useStockSearchController", () => ({
  useStockSearchController: () => ({
    inputValue: "",
    normalizedInput: "",
    currentResults: [],
    isPending: false,
    isError: false,
    error: null,
    retry: vi.fn(),
    setInputValue: vi.fn(),
    clear: vi.fn(),
  }),
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <WatchlistPage />
    </MemoryRouter>,
  );
}

describe("WatchlistPage", () => {
  beforeEach(() => {
    mocks.add.mockReset().mockResolvedValue({});
    mocks.remove.mockReset().mockResolvedValue({});
    mocks.addAlert.mockReset().mockResolvedValue({});
    mocks.deleteAlert.mockReset().mockResolvedValue({});
    mocks.refetch.mockReset().mockResolvedValue({ isError: false });
  });

  it("shows every stock once in the default all view", () => {
    renderPage();

    expect(screen.getByRole("heading", { name: "我的自选" })).toBeInTheDocument();
    expect(screen.getByLabelText("自选总数 3，3 只已有行情")).toBeInTheDocument();
    expect(screen.getByLabelText("上涨 1，占有效行情 33%")).toBeInTheDocument();
    expect(screen.getByLabelText("平盘 1，占有效行情 33%")).toBeInTheDocument();
    expect(screen.getByLabelText("下跌 1，占有效行情 33%")).toBeInTheDocument();
    expect(screen.getAllByText(/^[0-9]+$/, { selector: ".watchlist-page__market-count" })
      .map((node) => node.textContent)).toEqual(["3", "1", "1", "1", "0"]);
    expect(screen.getByText("1518.20", { selector: ".watchlist-page__price" })).toHaveClass("is-up");
    expect(screen.getByText("121.56", { selector: ".watchlist-page__price" })).toHaveClass("is-down");
    expect(screen.getByText("3.25", { selector: ".watchlist-page__price" })).toHaveClass("is-flat");
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: /五粮液/ })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: /大唐发电/ })).toHaveLength(1);
    expect(screen.getByRole("link", { name: /贵州茅台/ })).toHaveAttribute("href", "/stock/600519");
    expect(screen.getAllByText("白酒概念")).toHaveLength(2);
    expect(screen.getByText("茅指数")).toBeInTheDocument();
  });

  it("groups stocks by every concept and puts unclassified stocks into 其他", () => {
    renderPage();

    fireEvent.click(screen.getByText("概念分组"));

    expect(screen.getByRole("button", { name: /白酒概念.*2 只/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /茅指数.*1 只/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /其他.*1 只/ })).toBeInTheDocument();
    expect(within(screen.getByLabelText("白酒概念涨跌概览")).getByText("涨 1")).toBeInTheDocument();
    expect(within(screen.getByLabelText("白酒概念涨跌概览")).getByText("平 0")).toBeInTheDocument();
    expect(within(screen.getByLabelText("白酒概念涨跌概览")).getByText("跌 1")).toBeInTheDocument();
    expect(within(screen.getByLabelText("茅指数涨跌概览")).getByText("涨 1")).toBeInTheDocument();
    expect(within(screen.getByLabelText("其他涨跌概览")).getByText("平 1")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })).toHaveLength(2);
    expect(screen.getAllByRole("link", { name: /大唐发电/ })).toHaveLength(1);
  });

  it("filters by concept and supports collapsing a concept group", () => {
    renderPage();

    fireEvent.change(screen.getByRole("textbox", { name: "筛选自选股" }), {
      target: { value: "白酒概念" },
    });
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })).toHaveLength(1);
    expect(screen.getAllByRole("link", { name: /五粮液/ })).toHaveLength(1);
    expect(screen.queryByRole("link", { name: /大唐发电/ })).not.toBeInTheDocument();
    expect(screen.getByText("筛选到 2 只股票")).toBeInTheDocument();
    expect(screen.getByText("当前显示 2 只")).toBeInTheDocument();

    fireEvent.click(screen.getByText("概念分组"));
    const groupButton = screen.getByRole("button", { name: /白酒概念.*2 只/ });
    const groupSection = groupButton.closest("section");
    expect(groupSection).not.toBeNull();
    expect(within(groupSection as HTMLElement).getAllByRole("link")).toHaveLength(2);

    fireEvent.click(groupButton);
    expect(groupButton).toHaveAttribute("aria-expanded", "false");
    expect(within(groupSection as HTMLElement).queryByRole("link")).not.toBeInTheDocument();
  });

  it("filters by market direction and keeps the final result count in sync", () => {
    renderPage();

    const marketFilter = screen.getByLabelText("按行情状态筛选");
    fireEvent.click(within(marketFilter).getByText("下跌"));

    expect(screen.getByRole("link", { name: /五粮液/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /贵州茅台/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /大唐发电/ })).not.toBeInTheDocument();
    expect(screen.getByText("筛选到 1 只股票")).toBeInTheDocument();
    expect(screen.getByText("当前显示 1 只")).toBeInTheDocument();
  });

  it("sorts the all view and supports switching sort direction", () => {
    renderPage();

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "排序指标" }));
    fireEvent.click(screen.getByText("最新价", { selector: ".ant-select-item-option-content" }));

    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual([
      "贵州茅台600519",
      "五粮液000858",
      "大唐发电601991",
    ]);

    fireEvent.click(screen.getByRole("button", { name: "切换为升序" }));
    expect(screen.getAllByRole("link").map((link) => link.textContent)).toEqual([
      "大唐发电601991",
      "五粮液000858",
      "贵州茅台600519",
    ]);
  });

  it("opens a concept group from the table and can reset the active filter", () => {
    renderPage();

    fireEvent.click(screen.getAllByRole("button", { name: "查看白酒概念分组" })[0]);

    expect(screen.getByRole("button", { name: /白酒概念.*2 只/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /茅指数.*1 只/ })).not.toBeInTheDocument();
    expect(screen.getByText("筛选到 2 只股票")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "重置筛选" }));

    expect(screen.getByRole("button", { name: /白酒概念.*2 只/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /茅指数.*1 只/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /其他.*1 只/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "重置筛选" })).not.toBeInTheDocument();
  });

  it("can collapse all groups and focus on a single concept", () => {
    renderPage();

    fireEvent.click(screen.getByText("概念分组"));
    fireEvent.click(screen.getByRole("button", { name: "全部收起" }));
    expect(screen.queryByRole("link", { name: /贵州茅台/ })).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /只/ })).toHaveLength(3);

    fireEvent.click(screen.getByRole("button", { name: "全部展开" }));
    expect(screen.getAllByRole("link", { name: /贵州茅台/ })).toHaveLength(2);

    fireEvent.mouseDown(screen.getByRole("combobox", { name: "定位概念分组" }));
    fireEvent.click(screen.getByText("茅指数（1）", { selector: ".ant-select-item-option-content" }));

    expect(screen.getByRole("button", { name: /茅指数.*1 只/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /白酒概念.*2 只/ })).not.toBeInTheDocument();
    expect(screen.getByText("当前显示 1 只")).toBeInTheDocument();
  });

  it("supports exporting watchlist to CSV and selecting stocks for batch backtest", () => {
    renderPage();

    expect(screen.getByRole("button", { name: /导出 CSV/ })).toBeInTheDocument();

    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[1]);

    expect(screen.getByText("已选 1 只")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /批量回测/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /清空选择/ }));
    expect(screen.queryByText("已选 1 只")).not.toBeInTheDocument();
  });
});
