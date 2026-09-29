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
  const timeScale = {
    setVisibleRange: vi.fn(),
    fitContent: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: vi.fn((id: "left" | "right") => priceScales[id]),
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
        }),
        leftPriceScale: expect.objectContaining({ visible: true }),
        rightPriceScale: expect.objectContaining({ visible: true }),
      }),
    );

    // Verify right axis (price) scale margins
    expect(mocks.priceScales.right.applyOptions).toHaveBeenCalledWith(
      expect.objectContaining({
        visible: true,
        scaleMargins: { top: 0.05, bottom: 0.22 },
      }),
    );

    // Verify left axis (volume) scale margins
    expect(mocks.priceScales.left.applyOptions).toHaveBeenCalledWith(
      expect.objectContaining({
        visible: true,
        scaleMargins: { top: 0.82, bottom: 0 },
      }),
    );

    // Check HUD shows latest data
    expect(screen.getByText("09:31")).toBeInTheDocument();
    expect(screen.getAllByText("10.60").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("10.52")).toBeInTheDocument();
    expect(screen.getByText("15.00万")).toBeInTheDocument();
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
});
