import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Screener from ".";

const mocks = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  setSelectedCodes: vi.fn(),
  cancel: vi.fn(),
  useRunStrategy: vi.fn(),
  useScreen: vi.fn(),
}));

const filters = {
  page: 1,
  page_size: 50,
  sort_by: "market_cap",
  sort_order: "desc" as const,
};
let currentFilters = filters;
const candidates = {
  items: [
    { code: "600519", name: "贵州茅台" },
    { code: "000001", name: "平安银行" },
  ],
  total: 2,
  page: 1,
  page_size: 50,
  stock_master_complete: true,
  sw_industry_coverage: 0.94,
  exchange_industry_coverage: 1,
};
const strategy = {
  key: "bull_trend",
  name: "多头趋势",
  description: "均线多头排列",
  scenario: "趋势选股",
  risk_level: "medium",
  parameters: { fast_period: 5 },
  parameter_definitions: [{
    key: "fast_period",
    type: "integer",
    label: "快速周期",
    description: "短周期均线",
    default: 5,
    minimum: 2,
    maximum: 60,
    step: 1,
  }],
};

vi.mock("../../api/queries", () => ({
  useIndustries: () => ({ data: [], error: null, refetch: vi.fn() }),
  useScreenerStrategies: () => ({ data: [strategy], error: null, isLoading: false, refetch: vi.fn() }),
  useRunScreenerStrategy: () => mocks.useRunStrategy(),
  useScreenerScreen: () => mocks.useScreen(),
}));
vi.mock("../../styles/ui", () => ({
  useStyles: () => ({
    cardStyle: {},
    pageContainerStyle: {},
    pageDescriptionStyle: {},
    pageHeaderStyle: {},
    pageTitleStyle: {},
    sectionCardBodyStyle: {},
  }),
}));
vi.mock("./useScreenerFilterController", () => ({
  useScreenerFilterController: () => ({
    appliedState: { filters: currentFilters },
    filters: currentFilters,
    showPercentile: false,
    pePercentileMax: 50,
    pbPercentileMax: 50,
    applyPreset: vi.fn(),
    applySavedFilter: vi.fn(),
    setFilters: vi.fn(),
    handlePageChange: vi.fn(),
    handlePbPercentileMaxChange: vi.fn(),
    handlePePercentileMaxChange: vi.fn(),
    handleReset: vi.fn(),
    handleSearch: vi.fn(),
    handleShowPercentileChange: vi.fn(),
    handleSortChange: vi.fn(),
  }),
}));
vi.mock("./useScreenerBatchController", () => ({
  useScreenerBatchController: () => ({
    selectedCodes: [],
    setSelectedCodes: mocks.setSelectedCodes,
    clearSelection: vi.fn(),
    handleAddSelectedToWatchlist: vi.fn(),
    handleBatchAnalyze: vi.fn(),
    isAddingWatchlist: false,
    isBatchAnalyzing: false,
    analysisProgress: "",
  }),
}));
vi.mock("./useScreenerPercentiles", () => ({
  useScreenerPercentiles: () => ({
    displayData: candidates,
    percentileMap: new Map(),
    isPending: false,
  }),
}));
vi.mock("./FilterPanel", () => ({ default: () => <div>筛选面板</div> }));
vi.mock("./SavedFilterToolbar", () => ({ default: () => <div>保存筛选</div> }));
vi.mock("./ScreenerBatchActions", () => ({ default: () => <div>批量操作</div> }));
vi.mock("./ResultsTable", () => ({
  default: ({ data }: { data?: typeof candidates }) => (
    <div data-testid="result-codes">{data?.items.map((item) => item.code).join(",")}</div>
  ),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolver, rejecter) => {
    resolve = resolver;
    reject = rejecter;
  });
  return { promise, reject, resolve };
}

const completedResult = {
  strategy_key: "bull_trend",
  strategy_name: "多头趋势",
  strategy_version: "1.0.0",
  definition_hash: "sha256:1234567890abcdef1234567890",
  parameters: { fast_period: 12 },
  matches: [{ code: "600519", signal_date: "2026-08-17", target_position: 1 }],
  matched_codes: ["600519"],
  evaluated: 2,
  failed: {},
  matched_items: [candidates.items[0]],
};

describe("Screener strategy workflow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    currentFilters = filters;
    mocks.useRunStrategy.mockReturnValue({ mutateAsync: mocks.mutateAsync, isPending: false });
    mocks.useScreen.mockReturnValue({
      data: candidates,
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
  });

  it("submits edited parameters, renders progress, and filters matches", async () => {
    const execution = deferred<typeof completedResult>();
    mocks.mutateAsync.mockImplementation((request) => {
      request.onStarted(mocks.cancel);
      request.onProgress({ type: "progress", completed: 1, total: 2, matched: 1, failed: 0 });
      return execution.promise;
    });
    render(<MemoryRouter><Screener /></MemoryRouter>);

    expect(screen.getByText("主表完整")).toBeInTheDocument();
    expect(screen.getByText("申万覆盖 94%")).toBeInTheDocument();
    expect(screen.getByText("交易所行业 100%")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.change(screen.getByRole("spinbutton", { name: "快速周期" }), { target: { value: "12" } });
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));

    expect(mocks.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      strategy_key: "bull_trend",
      parameters: { fast_period: 12 },
      codes: ["600519", "000001"],
      scan_limit: 50,
      candidate_items: candidates.items,
    }));
    expect(await screen.findByText(/策略扫描中：1\/2，命中 1，失败 0/)).toBeInTheDocument();

    execution.resolve(completedResult);
    expect(await screen.findByText(/多头趋势@1.0.0：命中 1\/2 只/)).toBeInTheDocument();
    expect(mocks.setSelectedCodes).toHaveBeenCalledWith(["600519"]);
    expect(screen.getByTestId("result-codes")).toHaveTextContent("600519");

    fireEvent.click(screen.getByRole("button", { name: "显示全部" }));
    expect(screen.getByTestId("result-codes")).toHaveTextContent("600519,000001");
  });

  it("cancels an active scan from the progress alert", async () => {
    const execution = deferred<typeof completedResult>();
    mocks.cancel.mockImplementation(() => execution.reject(new Error("已取消")));
    mocks.mutateAsync.mockImplementation((request) => {
      request.onStarted(mocks.cancel);
      request.onProgress({ type: "progress", completed: 1, total: 2, matched: 0, failed: 0 });
      return execution.promise;
    });
    render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));
    fireEvent.click(await screen.findByRole("button", { name: "取消扫描" }));

    expect(mocks.cancel).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(screen.queryByText(/策略扫描中/)).not.toBeInTheDocument());
    expect(screen.queryByText(/多头趋势@1.0.0/)).not.toBeInTheDocument();
  });

  it("cancels and ignores an old scan when the applied filters change", async () => {
    const execution = deferred<typeof completedResult>();
    mocks.mutateAsync.mockImplementation((request) => {
      request.onStarted(mocks.cancel);
      request.onProgress({ type: "progress", completed: 1, total: 2, matched: 0, failed: 0 });
      return execution.promise;
    });
    const view = render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));
    expect(await screen.findByText(/策略扫描中/)).toBeInTheDocument();

    currentFilters = { ...filters, page: 2 };
    view.rerender(<MemoryRouter><Screener /></MemoryRouter>);
    await waitFor(() => expect(mocks.cancel).toHaveBeenCalledTimes(1));
    execution.resolve(completedResult);

    await waitFor(() => expect(screen.queryByText(/策略扫描中/)).not.toBeInTheDocument());
    expect(screen.queryByText(/多头趋势@1.0.0/)).not.toBeInTheDocument();
    expect(mocks.setSelectedCodes).not.toHaveBeenCalled();
  });

  it("passes the first-200 scan mode to the execution hook", async () => {
    mocks.mutateAsync.mockResolvedValue(completedResult);
    render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("radio", { name: "前 200 候选" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));

    await waitFor(() => expect(mocks.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      scan_limit: 200,
      candidate_filters: filters,
    })));
  });

  it("shows matches from the full 200-candidate scope even when they are outside the current page", async () => {
    mocks.mutateAsync.mockResolvedValue({
      ...completedResult,
      matches: [{ code: "300750", signal_date: "2026-08-16", target_position: 1 }],
      matched_codes: ["300750"],
      matched_items: [{ code: "300750", name: "宁德时代" }],
    });
    render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("radio", { name: "前 200 候选" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));

    expect(await screen.findByText(/多头趋势@1.0.0：命中 1\/2 只/)).toBeInTheDocument();
    expect(screen.getByTestId("result-codes")).toHaveTextContent("300750");
  });

  it("does not execute current-page codes while refreshed filter results are still loading", () => {
    const view = render(<MemoryRouter><Screener /></MemoryRouter>);
    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));

    mocks.useScreen.mockReturnValue({
      data: candidates,
      isLoading: false,
      isFetching: true,
      error: null,
      refetch: vi.fn(),
    });
    view.rerender(<MemoryRouter><Screener /></MemoryRouter>);

    expect(screen.getByRole("button", { name: "执行策略选股" })).toBeDisabled();
  });

  it("marks partial data failures as a warning instead of a successful scan", async () => {
    mocks.mutateAsync.mockResolvedValue({
      ...completedResult,
      failed: { "000001": "temporary" },
    });
    render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));

    const title = await screen.findByText(/1 只数据失败/);
    expect(title.closest(".ant-alert")).toHaveClass("ant-alert-warning");
  });

  it("can start a first-200 scan even when the current pagination page is empty", async () => {
    mocks.useScreen.mockReturnValue({
      data: { ...candidates, items: [], total: 120, page: 4 },
      isLoading: false,
      isFetching: false,
      error: null,
      refetch: vi.fn(),
    });
    mocks.mutateAsync.mockResolvedValue({
      ...completedResult,
      matches: [],
      matched_codes: [],
      matched_items: [],
    });
    render(<MemoryRouter><Screener /></MemoryRouter>);

    fireEvent.click(screen.getByRole("button", { name: "多头趋势" }));
    fireEvent.click(screen.getByRole("radio", { name: "前 200 候选" }));
    fireEvent.click(screen.getByRole("button", { name: "执行策略选股" }));

    await waitFor(() => expect(mocks.mutateAsync).toHaveBeenCalledWith(expect.objectContaining({
      codes: [],
      scan_limit: 200,
    })));
  });
});
