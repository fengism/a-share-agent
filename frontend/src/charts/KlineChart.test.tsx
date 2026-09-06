import { render } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
  const timeScale = {
    fitContent: vi.fn(),
    coordinateToLogical: vi.fn(),
    setVisibleLogicalRange: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn(),
    applyOptions: vi.fn(),
    priceScale: vi.fn((id: "left" | "right") => priceScales[id]),
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
    timeScale,
    chart,
    createChart: vi.fn(() => chart),
    createSeriesMarkers: vi.fn(() => ({ setMarkers: vi.fn() })),
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

  it("shows turnover amount on the left scale while keeping price on the right", () => {
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
        leftPriceScale: expect.objectContaining({ visible: true }),
        rightPriceScale: expect.objectContaining({ visible: true }),
      }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      1,
      "CandlestickSeries",
      expect.objectContaining({ priceScaleId: "right" }),
    );
    expect(mocks.chart.addSeries).toHaveBeenNthCalledWith(
      2,
      "HistogramSeries",
      expect.objectContaining({ priceScaleId: "left" }),
    );
    expect(mocks.priceScales.left.applyOptions).toHaveBeenCalledWith(
      expect.objectContaining({
        visible: true,
        scaleMargins: { top: 0.82, bottom: 0 },
      }),
    );
    expect(mocks.volumeSeries.setData).toHaveBeenCalledWith([
      expect.objectContaining({ value: 250_000_000 }),
    ]);
  });
});
