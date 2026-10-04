import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { APP_FONT_FAMILY } from "../theme/typography";
import IntradayChart from "./IntradayChart";

const mocks = vi.hoisted(() => {
  const priceSeries = {
    setData: vi.fn(),
    update: vi.fn(),
    applyOptions: vi.fn(),
    createPriceLine: vi.fn(),
    removePriceLine: vi.fn(),
  };
  const avgSeries = {
    setData: vi.fn(),
    update: vi.fn(),
    applyOptions: vi.fn(),
  };
  const volumeSeries = {
    setData: vi.fn(),
    update: vi.fn(),
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
  const timeScale = {
    setVisibleRange: vi.fn(),
    fitContent: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: vi.fn((id: "left" | "right") => priceScales[id]),
    panes: vi.fn(() => panes),
    timeScale: vi.fn(() => timeScale),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    remove: vi.fn(),
  };

  return {
    priceSeries,
    avgSeries,
    volumeSeries,
    priceScales,
    panes,
    timeScale,
    chart,
    createChart: vi.fn(() => chart),
  };
});

vi.mock("lightweight-charts", () => ({
  createChart: mocks.createChart,
  AreaSeries: "AreaSeries",
  HistogramSeries: "HistogramSeries",
  ColorType: { Solid: "Solid" },
  LineStyle: { Dotted: 1, Dashed: 2 },
}));

vi.mock("../styles/ui", () => ({
  useColors: () => ({
    accent: "#ff9900",
    border: "#d9d9d9",
    cardBg: "#ffffff",
    nestedBg: "#fafafa",
    textPrimary: "#1f1f1f",
    textSecondary: "#595959",
    textMuted: "#8c8c8c",
    primary: "#1677ff",
    up: "#f5222d",
    down: "#52c41a",
  }),
}));

describe("IntradayChart", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.chart.addSeries
      .mockReturnValueOnce(mocks.priceSeries)
      .mockReturnValueOnce(mocks.avgSeries)
      .mockReturnValueOnce(mocks.volumeSeries);
  });

  it("configures font family and scale margins aligned with KlineChart", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 10.5, avg_price: 10.45, volume: 120000, amount: 1260000, change_pct: 5.0 },
          { time: "09:31:00", price: 10.6, avg_price: 10.52, volume: 150000, amount: 1590000, change_pct: 6.0 },
        ]}
        prevClose={10.0}
        height={380}
      />,
    );

    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        height: 380 - 32,
        layout: expect.objectContaining({
          fontFamily: APP_FONT_FAMILY,
          // 分窗格分隔线跟随主题，否则深色主题下是一条浅色刺眼线
          panes: expect.objectContaining({ separatorColor: expect.any(String) }),
        }),
        rightPriceScale: expect.objectContaining({ visible: true }),
        // 左轴只能在 chart 级整体关闭：在非 0 窗格单独隐藏坐标轴会让整图不渲染
        leftPriceScale: expect.objectContaining({ visible: false }),
      }),
    );

    // 价格与成交量分处两个窗格，各自独立刻度
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      1,
      "AreaSeries",
      expect.objectContaining({ priceScaleId: "right" }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      2,
      "AreaSeries",
      expect.objectContaining({ priceScaleId: "right" }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      3,
      "HistogramSeries",
      expect.objectContaining({ priceScaleId: "right" }),
      1,
    );
    expect(mocks.chart.priceScale).toHaveBeenCalledWith("right", 0);
    expect(mocks.chart.priceScale).toHaveBeenCalledWith("right", 1);
    expect(mocks.panes[0].setStretchFactor).toHaveBeenCalledWith(0.72);
    expect(mocks.panes[1].setStretchFactor).toHaveBeenCalledWith(0.28);
    // 任何窗格都不得单独隐藏坐标轴（lightweight-charts 5.2.1 会因此整图崩溃）
    const hiddenAxisCalls = (["left", "right"] as const).flatMap((side) =>
      mocks.priceScales[side].applyOptions.mock.calls.filter(
        ([opts]) => (opts as { visible?: boolean })?.visible === false,
      ),
    );
    expect(hiddenAxisCalls).toEqual([]);

    // Check HUD shows latest data
    expect(screen.getByText("09:31")).toBeInTheDocument();
    expect(screen.getByText("10.52")).toBeInTheDocument();
    expect(screen.getAllByText("15.00万").length).toBeGreaterThanOrEqual(1);
  });

  it("respects showAvgLine and showPrevCloseLine toggle props", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 10.5, avg_price: 10.45, volume: 120000, amount: 1260000, change_pct: 5.0 },
        ]}
        prevClose={10.0}
        showAvgLine={false}
        showPrevCloseLine={false}
      />,
    );

    expect(screen.queryByText("均价线")).not.toBeInTheDocument();
    expect(screen.queryByText(/昨收 10.00/)).not.toBeInTheDocument();
    expect(mocks.priceSeries.createPriceLine).not.toHaveBeenCalled();
    expect(mocks.avgSeries.setData).toHaveBeenCalledWith([]);
  });

  it("supports keyboard navigation with arrow keys and escape", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 10.5, avg_price: 10.45, volume: 120000, amount: 1260000, change_pct: 5.0 },
          { time: "09:31:00", price: 10.6, avg_price: 10.52, volume: 150000, amount: 1590000, change_pct: 6.0 },
        ]}
        prevClose={10.0}
      />,
    );

    const region = screen.getByRole("region", { name: "分时图交互区" });
    // Navigate backwards
    fireEvent.keyDown(region, { key: "ArrowLeft" });
    expect(screen.getByText("09:30")).toBeInTheDocument();
    expect(screen.getAllByText("10.50").length).toBeGreaterThanOrEqual(1);

    // Navigate forwards
    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(screen.getByText("09:31")).toBeInTheDocument();
    expect(screen.getAllByText("10.60").length).toBeGreaterThanOrEqual(1);

    // Escape resets
    fireEvent.keyDown(region, { key: "Escape" });
    expect(screen.getByText("09:31")).toBeInTheDocument();
  });

  it("configures symmetric autoscale around prevClose and suppresses avgSeries autoscale", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 10.5, avg_price: 10.45, volume: 120000, amount: 1260000, change_pct: 5.0 },
        ]}
        prevClose={10.0}
      />,
    );

    const priceSeriesConfig = mocks.chart.addSeries.mock.calls[0][1];
    expect(priceSeriesConfig.autoscaleInfoProvider).toBeDefined();

    // Call autoscaleInfoProvider with an asymmetric range [9.8, 10.5] (prevClose=10.0, maxDelta=0.5)
    const result = priceSeriesConfig.autoscaleInfoProvider(() => ({
      priceRange: { minValue: 9.8, maxValue: 10.5 },
    }));
    expect(result).toEqual({
      priceRange: {
        minValue: 10.0 - 0.5, // 9.5
        maxValue: 10.0 + 0.5, // 10.5
      },
    });

    // Check avgSeries autoscaleInfoProvider returns null
    const avgSeriesConfig = mocks.chart.addSeries.mock.calls[1][1];
    expect(avgSeriesConfig.autoscaleInfoProvider).toBeDefined();
    expect(avgSeriesConfig.autoscaleInfoProvider()).toBeNull();
  });

  it("adapts visible range for HK market up to 16:00", () => {
    render(
      <IntradayChart
        data={[
          { time: "2024-05-10 09:30:00", price: 350.0, avg_price: 350.0, volume: 50000, amount: 17500000, change_pct: 0 },
        ]}
        prevClose={350.0}
        market="hk"
      />,
    );

    expect(mocks.timeScale.setVisibleRange).toHaveBeenCalledWith({
      from: Date.UTC(2024, 4, 10, 9, 30) / 1000,
      to: Date.UTC(2024, 4, 10, 16, 0) / 1000,
    });
  });

  it("displays amount in HUD when amount data is provided", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 10.5, avg_price: 10.45, volume: 120000, amount: 1260000, change_pct: 5.0 },
          { time: "09:31:00", price: 10.6, avg_price: 10.52, volume: 150000, amount: 2590000, change_pct: 6.0 },
        ]}
        prevClose={10.0}
      />,
    );

    // Initial HUD shows latest point (09:31) with amount
    expect(screen.getByText("分额:")).toBeInTheDocument();
    expect(screen.getAllByText("259.00万").length).toBeGreaterThanOrEqual(1);

    // Left percentage scale & Volume divider bar are rendered
    expect(screen.getByText("+6.00%")).toBeInTheDocument();
    expect(screen.getByText("0.00%")).toBeInTheDocument();
    expect(screen.getByText("-6.00%")).toBeInTheDocument();
    expect(screen.getByText("成交量 VOL")).toBeInTheDocument();

    const region = screen.getByRole("region", { name: "分时图交互区" });
    fireEvent.keyDown(region, { key: "ArrowLeft" });
    expect(screen.getAllByText("126.00万").length).toBeGreaterThanOrEqual(1);
  });

  it("handles same-price minute volume bar color using prevClose fallback", () => {
    render(
      <IntradayChart
        data={[
          { time: "09:30:00", price: 9.8, avg_price: 9.8, volume: 10000, amount: 98000, change_pct: -2 },
          { time: "09:31:00", price: 9.8, avg_price: 9.8, volume: 20000, amount: 196000, change_pct: -2 },
        ]}
        prevClose={10.0}
      />,
    );

    // Second bar has price 9.8 === prev price 9.8.
    // Since 9.8 < prevClose (10.0), it should be colored as down color, not up.
    const calls = mocks.volumeSeries.setData.mock.calls;
    const lastCall = calls[calls.length - 1][0];
    expect(lastCall).toHaveLength(2);
    expect(lastCall[1].color).toBe("rgba(82,196,26,0.38)");
    expect(lastCall[1].color).toBe(lastCall[0].color);
  });
});
