import { act, fireEvent, render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KlineItem } from "../types/stock";
import KlineChart from "./KlineChart";

const mocks = vi.hoisted(() => {
  const candleSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  const volumeSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  const priceScales = {
    left: { applyOptions: vi.fn() },
    right: { applyOptions: vi.fn() },
  };
  const panes = [
    { setStretchFactor: vi.fn(), setHeight: vi.fn() },
    { setStretchFactor: vi.fn(), setHeight: vi.fn() },
  ];
  const seriesMarkersApi = {
    setMarkers: vi.fn(),
  };
  const timeScale = {
    fitContent: vi.fn(),
    coordinateToLogical: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
    getVisibleLogicalRange: vi.fn(() => ({ from: 0, to: 100 })),
    subscribeVisibleLogicalRangeChange: vi.fn(),
    unsubscribeVisibleLogicalRangeChange: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: vi.fn((id: "left" | "right") => priceScales[id]),
    panes: vi.fn(() => panes),
    timeScale: vi.fn(() => timeScale),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    removeSeries: vi.fn(),
    remove: vi.fn(),
  };

  return {
    candleSeries,
    volumeSeries,
    priceScales,
    panes,
    timeScale,
    chart,
    seriesMarkersApi,
    createChart: vi.fn(() => chart),
    createSeriesMarkers: vi.fn(() => seriesMarkersApi),
  };
});

vi.mock("lightweight-charts", () => ({
  createChart: mocks.createChart,
  createSeriesMarkers: mocks.createSeriesMarkers,
  CandlestickSeries: "CandlestickSeries",
  HistogramSeries: "HistogramSeries",
  LineSeries: "LineSeries",
  ColorType: { Solid: "Solid" },
  LineStyle: { Dashed: 2 },
}));

vi.mock("../styles/ui", () => ({
  useColors: () => ({
    accent: "#1677ff",
    border: "#d9d9d9",
    cardBg: "#ffffff",
    down: "#00a870",
    info: "#1677ff",
    pageBg: "#f5f5f5",
    primary: "#1677ff",
    textMuted: "#8c8c8c",
    textSecondary: "#595959",
    up: "#f5222d",
  }),
}));

describe("KlineChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.chart.addSeries
      .mockReturnValueOnce(mocks.candleSeries)
      .mockReturnValueOnce(mocks.volumeSeries)
      .mockReturnValue({ setData: vi.fn(), applyOptions: vi.fn() });
  });

  it("splits price and volume into separate panes with independent axes", () => {
    render(
      <KlineChart
        height={500}
        data={[{
          date: "2026-08-28",
          open: 10,
          close: 10.5,
          high: 10.8,
          low: 9.9,
          volume: 1_000,
          amount: 250_000_000,
          amplitude: null,
          turnover_pct: null,
          change_pct: null,
        }]}
      />,
    );

    // 价格与均线留在 0 号窗格，成交量与量均线放到 1 号窗格
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      1,
      "CandlestickSeries",
      expect.objectContaining({ priceScaleId: "right" }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      2,
      "HistogramSeries",
      expect.objectContaining({ priceScaleId: "right" }),
      1,
    );
    const volumePaneCalls = mocks.chart.addSeries.mock.calls.filter(
      (call) => call[2] === 1,
    );
    // 量均线也应随成交量进入下窗格
    expect(volumePaneCalls.length).toBeGreaterThanOrEqual(2);

    // 两个窗格各自的右轴（价格轴 / 成交量轴）都要配置
    expect(mocks.chart.priceScale).toHaveBeenCalledWith("right", 0);
    expect(mocks.chart.priceScale).toHaveBeenCalledWith("right", 1);

    // lightweight-charts 5.2.1：判断要不要画轴只读 0 号窗格的 visible，却对所有窗格
    // ensureNotNull(轴 widget)。在非 0 窗格隐藏任一坐标轴会让每帧 draw 抛
    // "Value is null"、整张图空白，所以左轴只能整体关闭，且任何窗格都不得单独隐藏轴。
    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        leftPriceScale: expect.objectContaining({ visible: false }),
        rightPriceScale: expect.objectContaining({ visible: true }),
      }),
    );
    const hiddenAxisCalls = (["left", "right"] as const).flatMap((side) =>
      mocks.priceScales[side].applyOptions.mock.calls.filter(
        ([opts]) => (opts as { visible?: boolean })?.visible === false,
      ),
    );
    expect(hiddenAxisCalls).toEqual([]);

    // 窗格高度按比例分配：必须用 stretchFactor，写死像素会挤掉时间轴导致整图不渲染
    expect(mocks.panes[0].setStretchFactor).toHaveBeenCalledWith(0.72);
    expect(mocks.panes[1].setStretchFactor).toHaveBeenCalledWith(0.28);
    expect(mocks.panes[0].setHeight).not.toHaveBeenCalled();
    expect(mocks.panes[1].setHeight).not.toHaveBeenCalled();
  });

  it("keeps the price series on the right axis and the volume values on the chart", () => {
    render(
      <KlineChart
        data={[{
          date: "2026-08-28",
          open: 10,
          close: 10.5,
          high: 10.8,
          low: 9.9,
          volume: 1_000,
          amount: 250_000_000,
          amplitude: null,
          turnover_pct: null,
          change_pct: null,
        }]}
      />,
    );

    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        leftPriceScale: expect.anything(),
        rightPriceScale: expect.anything(),
      }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      1,
      "CandlestickSeries",
      expect.objectContaining({ priceScaleId: "right" }),
    );
    expect(mocks.volumeSeries.setData).toHaveBeenCalledWith([
      expect.objectContaining({ value: 250_000_000 }),
    ]);
  });

  it("handles quick range buttons (1月, 3月, 全部)", () => {
    const { getByRole } = render(
      <KlineChart
        data={Array.from({ length: 100 }, (_, i) => ({
          date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
          open: 10 + i,
          close: 11 + i,
          high: 12 + i,
          low: 9 + i,
          volume: 1000 + i,
        })) as unknown as KlineItem[]}
      />,
    );

    fireEvent.click(getByRole("button", { name: "1月" }));
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith(
      expect.objectContaining({ from: 100 - 22, to: 102 }),
    );

    fireEvent.click(getByRole("button", { name: "全部" }));
    expect(mocks.timeScale.fitContent).toHaveBeenCalled();
  });

  it("requests earlier history only once when the viewport reaches the left edge", () => {
    const onReachLeftEdge = vi.fn();
    const { rerender } = render(
      <KlineChart
        onReachLeftEdge={onReachLeftEdge}
        data={Array.from({ length: 100 }, (_, i) => ({
          date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
          open: 10 + i,
          close: 11 + i,
          high: 12 + i,
          low: 9 + i,
          volume: 1000 + i,
        })) as unknown as KlineItem[]}
      />,
    );

    const emitRange = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0]?.[0] as
      | ((range: { from: number; to: number } | null) => void)
      | undefined;
    expect(emitRange).toBeTypeOf("function");

    emitRange?.({ from: 40, to: 120 });
    expect(onReachLeftEdge).not.toHaveBeenCalled();

    emitRange?.({ from: 2, to: 90 });
    emitRange?.({ from: 0, to: 88 });
    expect(onReachLeftEdge).toHaveBeenCalledTimes(1);

    // 回到中间后可再次触发，支持继续向前扩充
    emitRange?.({ from: 30, to: 100 });
    emitRange?.({ from: 1, to: 70 });
    expect(onReachLeftEdge).toHaveBeenCalledTimes(2);

    // 达到上限后不再请求
    rerender(
      <KlineChart
        onReachLeftEdge={onReachLeftEdge}
        historyLimitReached
        data={Array.from({ length: 120 }, (_, i) => ({
          date: `2026-01-${String((i % 28) + 1).padStart(2, "0")}`,
          open: 10 + i,
          close: 11 + i,
          high: 12 + i,
          low: 9 + i,
          volume: 1000 + i,
        })) as unknown as KlineItem[]}
      />,
    );
    const emitAfterRerender = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls.at(-1)?.[0] as
      | ((range: { from: number; to: number } | null) => void)
      | undefined;
    emitAfterRerender?.({ from: 0, to: 90 });
    expect(onReachLeftEdge).toHaveBeenCalledTimes(2);
  });

  it("keeps the viewport anchored when earlier bars are prepended", () => {
    const buildData = (count: number, dayOffset = 0) =>
      Array.from({ length: count }, (_, i) => ({
        date: `2026-0${1 + Math.floor((i + dayOffset) / 28)}-${String(((i + dayOffset) % 28) + 1).padStart(2, "0")}`,
        open: 10 + i,
        close: 11 + i,
        high: 12 + i,
        low: 9 + i,
        volume: 1000 + i,
      })) as unknown as KlineItem[];

    const { rerender } = render(<KlineChart data={buildData(100)} viewKey="600519-daily-qfq" />);
    mocks.timeScale.setVisibleLogicalRange.mockClear();

    const emitRange = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0]?.[0] as
      | ((range: { from: number; to: number } | null) => void)
      | undefined;
    emitRange?.({ from: 2, to: 60 });

    // 补齐更早的 50 根后，视窗整体平移 50 根而不是跳回最新（viewKey 不变）
    rerender(<KlineChart data={buildData(150)} viewKey="600519-daily-qfq" />);
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 52, to: 110 });
  });

  it("discards a pending history anchor when the stock changes", () => {
    const buildData = (count: number) =>
      Array.from({ length: count }, (_, i) => ({
        date: new Date(Date.UTC(2016, 0, 4) + i * 86400000).toISOString().slice(0, 10),
        open: 10 + i,
        close: 11 + i,
        high: 12 + i,
        low: 9 + i,
        volume: 1000 + i,
      })) as unknown as KlineItem[];

    const { rerender } = render(<KlineChart data={buildData(100)} viewKey="600519-daily-qfq" />);
    mocks.timeScale.setVisibleLogicalRange.mockClear();

    const emitRange = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0]?.[0] as
      | ((range: { from: number; to: number } | null) => void)
      | undefined;
    // 触底记录锚点，但在数据回来之前切换标的
    emitRange?.({ from: 2, to: 60 });
    rerender(<KlineChart data={buildData(300)} viewKey="000001-daily-qfq" />);

    // 新标的走默认"显示最近 80 根"，而不是被上一只票的锚点平移
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 220, to: 302 });
  });

  it("discards a pending history anchor when data shrinks instead of growing", () => {
    const buildData = (count: number) =>
      Array.from({ length: count }, (_, i) => ({
        date: new Date(Date.UTC(2016, 0, 4) + i * 86400000).toISOString().slice(0, 10),
        open: 10 + i,
        close: 11 + i,
        high: 12 + i,
        low: 9 + i,
        volume: 1000 + i,
      })) as unknown as KlineItem[];

    const { rerender } = render(<KlineChart data={buildData(100)} viewKey="same" />);
    const emitRange = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0]?.[0] as
      | ((range: { from: number; to: number } | null) => void)
      | undefined;
    emitRange?.({ from: 2, to: 60 });

    // 数据变短（例如切到更短区间）后旧锚点失效，回缩到中间再触底应记录新锚点
    rerender(<KlineChart data={buildData(40)} viewKey="same" />);
    emitRange?.({ from: 20, to: 40 });
    emitRange?.({ from: 1, to: 30 });
    rerender(<KlineChart data={buildData(140)} viewKey="same" />);

    // 只按新锚点的 100 根差值平移，而不是叠加已失效的旧锚点
    expect(mocks.timeScale.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 101, to: 130 });
  });

  it("reuses the same chart instance when data changes instead of rebuilding it", () => {
    const buildData = (count: number) =>
      Array.from({ length: count }, (_, i) => ({
        date: `2026-0${1 + Math.floor(i / 28)}-${String((i % 28) + 1).padStart(2, "0")}`,
        open: 10 + i,
        close: 11 + i,
        high: 12 + i,
        low: 9 + i,
        volume: 1000 + i,
      })) as unknown as KlineItem[];

    const { rerender } = render(<KlineChart data={buildData(100)} />);
    expect(mocks.createChart).toHaveBeenCalledTimes(1);

    // 同 viewKey 下扩充历史：只 setData，不重建图表
    rerender(<KlineChart data={buildData(150)} viewKey="same" />);
    rerender(<KlineChart data={buildData(200)} viewKey="same" />);
    expect(mocks.createChart).toHaveBeenCalledTimes(1);
    expect(mocks.candleSeries.setData).toHaveBeenCalledTimes(3);
    expect(mocks.chart.remove).not.toHaveBeenCalled();

    // 高度变化才重建
    rerender(<KlineChart data={buildData(200)} viewKey="same" height={600} />);
    expect(mocks.createChart).toHaveBeenCalledTimes(2);
  });

  it("supports keyboard navigation with arrow keys and escape", () => {
    const { getByRole, getByText } = render(
      <KlineChart
        data={[
          { date: "2026-01-01", open: 10, close: 11, high: 12, low: 9, volume: 1000 },
          { date: "2026-01-02", open: 11, close: 12, high: 13, low: 10, volume: 1500 },
        ] as unknown as KlineItem[]}
      />,
    );

    const region = getByRole("region", { name: "K线图交互区" });
    // Navigate backwards
    fireEvent.keyDown(region, { key: "ArrowLeft" });
    expect(getByText("2026-01-01")).toBeInTheDocument();

    // Navigate forwards
    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(getByText("2026-01-02")).toBeInTheDocument();

    // Escape resets
    fireEvent.keyDown(region, { key: "Escape" });
    expect(getByText("2026-01-02")).toBeInTheDocument();
  });

  it("enables pressedMouseMove for panning and reserves brush zoom for Shift+drag", () => {
    const { getByRole, container } = render(
      <KlineChart
        data={[
          { date: "2026-01-01", open: 10, close: 11, high: 12, low: 9, volume: 1000 },
          { date: "2026-01-02", open: 11, close: 12, high: 13, low: 10, volume: 1500 },
        ] as unknown as KlineItem[]}
      />,
    );

    // Chart has pressedMouseMove: true enabled for standard canvas drag panning
    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        handleScroll: expect.objectContaining({ pressedMouseMove: true }),
      }),
    );

    const region = getByRole("region", { name: "K线图交互区" });
    const brush = container.querySelector(".kline-chart__plot > div:nth-child(2)") as HTMLElement;

    // Normal mousedown without Shift does NOT trigger brush zoom
    fireEvent.mouseDown(region, { button: 0, shiftKey: false, clientX: 100 });
    expect(brush?.style.display).toBe("none");

    // Mousedown with Shift triggers brush zoom
    fireEvent.mouseDown(region, { button: 0, shiftKey: true, clientX: 100 });
    expect(brush?.style.display).toBe("block");
  });

  it("automatically computes and displays high and low price markers for the visible range", () => {
    render(
      <KlineChart
        data={[
          { date: "2026-01-01", open: 10, close: 11, high: 12, low: 9, volume: 1000 },
          { date: "2026-01-02", open: 11, close: 15, high: 16.5, low: 10, volume: 1500 },
          { date: "2026-01-03", open: 15, close: 8, high: 15, low: 7.2, volume: 2000 },
        ] as unknown as KlineItem[]}
      />,
    );

    // Initial load sets markers including high and low
    expect(mocks.seriesMarkersApi.setMarkers).toHaveBeenCalled();
    const lastMarkers = mocks.seriesMarkersApi.setMarkers.mock.calls.at(-1)?.[0];
    expect(lastMarkers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          text: "高 16.50",
          shape: "arrowDown",
          position: "aboveBar",
        }),
        expect.objectContaining({
          text: "低 7.20",
          shape: "arrowUp",
          position: "belowBar",
        }),
      ]),
    );

    // When visible range changes to only index 0 (high=12, low=9)
    const emitRange = mocks.timeScale.subscribeVisibleLogicalRangeChange.mock.calls[0]?.[0];
    emitRange?.({ from: 0, to: 0 });

    const updatedMarkers = mocks.seriesMarkersApi.setMarkers.mock.calls.at(-1)?.[0];
    expect(updatedMarkers).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ text: "高 12.00" }),
        expect.objectContaining({ text: "低 9.00" }),
      ]),
    );
  });

  it("respects showHighLowMarkers=false", () => {
    render(
      <KlineChart
        data={[
          { date: "2026-01-01", open: 10, close: 11, high: 12, low: 9, volume: 1000 },
        ] as unknown as KlineItem[]}
        showHighLowMarkers={false}
      />,
    );

    const lastMarkers = mocks.seriesMarkersApi.setMarkers.mock.calls.at(-1)?.[0];
    const hasHighLow = (lastMarkers ?? []).some(
      (m: { text?: string }) => m.text?.startsWith("高") || m.text?.startsWith("低"),
    );
    expect(hasHighLow).toBe(false);
  });

  it("displays turnover, amplitude, and accurate changePct in HUD on crosshair move", () => {
    const { getByText, getAllByText } = render(
      <KlineChart
        data={[
          { date: "2026-01-01", open: 10, close: 10, high: 10.5, low: 9.8, volume: 1000, amount: 10000, turnover_pct: 1.2, amplitude: 7.0, change_pct: 0 },
          { date: "2026-01-02", open: 11, close: 11, high: 11.5, low: 10.8, volume: 2000, amount: 22000, turnover_pct: 2.5, amplitude: 7.0, change_pct: 10.0 },
        ] as unknown as KlineItem[]}
      />,
    );

    // Initial HUD displays latest bar (2026-01-02)
    expect(getByText(/换:/)).toBeInTheDocument();
    expect(getByText(/换手:/)).toBeInTheDocument();
    expect(getAllByText("2.50%").length).toBeGreaterThanOrEqual(1);
    expect(getByText(/振:/)).toBeInTheDocument();
    expect(getByText("7.00%")).toBeInTheDocument();
    expect(getByText("(+10.00%)")).toBeInTheDocument();

    // Crosshair move over the first bar (2026-01-01)
    const crosshairHandler = mocks.chart.subscribeCrosshairMove.mock.calls[0]?.[0];
    const seriesMap = new Map();
    seriesMap.set(mocks.candleSeries, { open: 10, high: 10.5, low: 9.8, close: 10 });
    seriesMap.set(mocks.volumeSeries, { value: 10000 });

    act(() => {
      crosshairHandler?.({
        time: { year: 2026, month: 1, day: 1 },
        seriesData: seriesMap,
      });
    });

    expect(getByText("2026-01-01")).toBeInTheDocument();
    expect(getAllByText("1.20%").length).toBeGreaterThanOrEqual(1);
    expect(getByText("(+0.00%)")).toBeInTheDocument();
  });
});
