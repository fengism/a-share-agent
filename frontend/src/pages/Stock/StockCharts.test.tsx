import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import dayjs from "dayjs";
import type { ChanlunResult } from "../../utils/chanlun";
import type { KlineItem } from "../../types/stock";
import StockCharts from "./StockCharts";

const mocks = vi.hoisted(() => ({ kline: vi.fn(), analyze: vi.fn() }));
vi.mock("../../api/queries", () => ({
  useKlineData: mocks.kline,
  useStockIntraday: () => ({ data: { items: [], prev_close: null }, isLoading: false, isFetching: false, error: null, refetch: vi.fn() }),
  useStockChipDistribution: vi.fn(),
}));
vi.mock("../../utils/chanlun", () => ({ analyzeChanlun: mocks.analyze }));
vi.mock("../../charts/LazyKlineChart", () => ({
  default: ({
    chanlun,
    viewKey,
    onReachLeftEdge,
    historyLimitReached,
  }: {
    chanlun: ChanlunResult | null;
    viewKey: string;
    onReachLeftEdge?: () => void;
    historyLimitReached?: boolean;
  }) => (
    <div data-testid="kline" data-overlay={chanlun ? "on" : "off"} data-view-key={viewKey}>
      {onReachLeftEdge ? (
        <button type="button" data-testid="kline-expand-history" onClick={onReachLeftEdge}>
          向左滑动
        </button>
      ) : null}
      <span data-testid="kline-history-limit">{historyLimitReached ? "limit" : "more"}</span>
    </div>
  ),
}));
vi.mock("../../charts/IndicatorSubCharts", () => ({ default: () => <div>指标图</div> }));
const bars = Array.from({ length: 12 }, (_, i) => ({ date: `2026-09-${String(i + 1).padStart(2, "0")}`, open: 10, close: 11, high: 12, low: 9, volume: 100 })) as KlineItem[];

describe("stock K-line Chanlun switch", () => {
  beforeEach(() => {
    mocks.kline.mockReset().mockReturnValue({ data: { items: bars }, isLoading: false, error: null, refetch: vi.fn() });
    mocks.analyze.mockReset().mockReturnValue({ bis: [], zss: [], mmds: [] });
  });

  it("only calculates the overlay when enabled without resetting the chart viewport key", () => {
    render(<StockCharts code="600519" />);
    const toggle = screen.getByRole("switch", { name: "缠论" });
    expect(toggle).not.toBeChecked();
    expect(mocks.analyze).not.toHaveBeenCalled();
    fireEvent.click(toggle);
    expect(mocks.analyze).toHaveBeenCalledWith(bars);
    expect(screen.getByTestId("kline")).toHaveAttribute("data-overlay", "on");
    expect(screen.getByTestId("kline")).toHaveAttribute("data-view-key", "600519-daily-qfq");
    fireEvent.click(toggle);
    expect(screen.getByTestId("kline")).toHaveAttribute("data-overlay", "off");
    expect(screen.getByTestId("kline")).toHaveAttribute("data-view-key", "600519-daily-qfq");
  });

  it("recalculates for changed period, adjustment and stock without another data source", () => {
    const { rerender } = render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByRole("switch", { name: "缠论" }));
    const weekly = bars.slice(0, 10);
    mocks.kline.mockReturnValue({ data: { items: weekly }, isLoading: false, error: null });
    fireEvent.click(screen.getByText("周K"));
    expect(mocks.kline).toHaveBeenLastCalledWith(
      "600519",
      "weekly",
      "qfq",
      true,
      { startDate: dayjs().subtract(1, "year").format("YYYYMMDD") },
    );
    expect(mocks.analyze).toHaveBeenLastCalledWith(weekly);
    const adjusted = [...weekly];
    mocks.kline.mockReturnValue({ data: { items: adjusted }, isLoading: false, error: null });
    fireEvent.click(screen.getByText("后复权"));
    expect(mocks.kline).toHaveBeenLastCalledWith(
      "600519",
      "weekly",
      "hfq",
      true,
      { startDate: dayjs().subtract(1, "year").format("YYYYMMDD") },
    );
    expect(mocks.analyze).toHaveBeenLastCalledWith(adjusted);
    mocks.kline.mockReturnValue({ data: { items: bars }, isLoading: false, error: null });
    rerender(<StockCharts code="000001" />);
    expect(mocks.kline).toHaveBeenLastCalledWith(
      "000001",
      "weekly",
      "hfq",
      true,
      { startDate: dayjs().subtract(1, "year").format("YYYYMMDD") },
    );
    expect(mocks.analyze).toHaveBeenLastCalledWith(bars);
  });

  it("retains the switch after visiting indicator tabs", () => {
    render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByRole("switch", { name: "缠论" }));
    fireEvent.click(screen.getByText("RSI"));
    expect(screen.queryByTestId("kline")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("K 线"));
    expect(screen.getByRole("switch", { name: "缠论" })).toBeChecked();
    expect(screen.getByTestId("kline")).toHaveAttribute("data-overlay", "on");
  });

  it("keeps a short series visible with a clear Chanlun hint", () => {
    mocks.kline.mockReturnValue({ data: { items: bars.slice(0, 9) }, isLoading: false, error: null });
    render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByRole("switch", { name: "缠论" }));
    expect(screen.getByRole("status")).toHaveTextContent("不足 10 根");
    expect(screen.getByTestId("kline")).toHaveAttribute("data-overlay", "off");
    expect(mocks.analyze).not.toHaveBeenCalled();
  });

  it("preserves empty and failed data states when enabled", () => {
    mocks.kline.mockReturnValue({ data: { items: [] }, isLoading: false, error: null });
    const { rerender } = render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByRole("switch", { name: "缠论" }));
    expect(screen.getByText("暂无 K 线数据")).toBeInTheDocument();
    mocks.kline.mockReturnValue({ isLoading: false, error: new Error("offline"), refetch: vi.fn() });
    rerender(<StockCharts code="600519" />);
    expect(screen.getByText("K 线数据加载失败")).toBeInTheDocument();
    expect(mocks.analyze).not.toHaveBeenCalled();
  });

  it("defaults to one year of history and extends by one year per left-edge request up to ten years", () => {
    render(<StockCharts code="600519" />);
    const rangeHint = () => screen.getByTestId("kline-history-range").textContent ?? "";
    expect(rangeHint()).toContain("近 1 年");
    expect(rangeHint()).toContain("最多 10 年");
    // 默认窗口：一年前
    expect(mocks.kline).toHaveBeenLastCalledWith(
      "600519",
      "daily",
      "qfq",
      true,
      { startDate: dayjs().subtract(1, "year").format("YYYYMMDD") },
    );

    // 左缘触底逐年前扩，最多 10 年
    for (let years = 2; years <= 10; years += 1) {
      fireEvent.click(screen.getByTestId("kline-expand-history"));
      expect(rangeHint()).toContain(years === 10 ? "已加载近 10 年" : `近 ${years} 年`);
    }
    expect(mocks.kline).toHaveBeenLastCalledWith(
      "600519",
      "daily",
      "qfq",
      true,
      { startDate: dayjs().subtract(10, "year").format("YYYYMMDD") },
    );
    // 到达上限后不再挂载扩充按钮
    expect(screen.queryByTestId("kline-expand-history")).not.toBeInTheDocument();
  });

  it("resets the history window when the stock or period changes", () => {
    render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByTestId("kline-expand-history"));
    expect(screen.getByTestId("kline-history-range")).toHaveTextContent("近 2 年");
    fireEvent.click(screen.getByText("周K"));
    expect(screen.getByTestId("kline-history-range")).toHaveTextContent("近 1 年");
  });

  it("renders intraday toolbar with toggles and refresh button when switching to intraday view", () => {
    render(<StockCharts code="600519" />);
    fireEvent.click(screen.getByText("分时"));
    expect(screen.getByRole("switch", { name: "均价线" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "昨收线" })).toBeChecked();
    expect(screen.getByRole("button", { name: /刷新/ })).toBeInTheDocument();
  });

  it("opens fullscreen modal when clicking fullscreen button and renders expanded chart", () => {
    render(<StockCharts code="600519" />);
    const fullscreenBtn = screen.getByRole("button", { name: "全屏查看图表" });
    expect(fullscreenBtn).toBeInTheDocument();
    fireEvent.click(fullscreenBtn);
    expect(screen.getByText("600519 · K 线图全屏")).toBeInTheDocument();
    const klineCharts = screen.getAllByTestId("kline");
    // One in background card, one in fullscreen modal
    expect(klineCharts.length).toBe(2);
    expect(klineCharts[1]).toHaveAttribute("data-view-key", "600519-daily-qfq-fullscreen");
  });
});
