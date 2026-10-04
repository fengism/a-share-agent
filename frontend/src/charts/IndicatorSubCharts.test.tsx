import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import IndicatorSubCharts from "./IndicatorSubCharts";

const mocks = vi.hoisted(() => {
  const lineSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  const histogramSeries = {
    setData: vi.fn(),
    applyOptions: vi.fn(),
  };
  const priceScales = {
    right: { applyOptions: vi.fn() },
  };
  const timeScale = {
    fitContent: vi.fn(),
  };
  const chart = {
    addSeries: vi.fn((seriesType: string) => {
      if (seriesType === "HistogramSeries") return histogramSeries;
      return lineSeries;
    }),
    applyOptions: vi.fn(),
    priceScale: vi.fn(() => priceScales.right),
    timeScale: vi.fn(() => timeScale),
    subscribeCrosshairMove: vi.fn(),
    unsubscribeCrosshairMove: vi.fn(),
    removeSeries: vi.fn(),
    remove: vi.fn(),
  };

  return {
    lineSeries,
    histogramSeries,
    chart,
    createChart: vi.fn(() => chart),
  };
});

vi.mock("lightweight-charts", () => ({
  createChart: mocks.createChart,
  HistogramSeries: "HistogramSeries",
  LineSeries: "LineSeries",
  ColorType: { Solid: "Solid" },
}));

const mockIndicatorsData = {
  series: {
    dates: ["2026-09-10", "2026-09-11", "2026-09-12"],
    dif: [0.5, 0.6, 0.7],
    dea: [0.4, 0.45, 0.5],
    macd_hist: [0.1, 0.15, 0.2],
    rsi: [55, 62, 68],
    k: [40, 50, 60],
    d: [35, 45, 55],
    j: [50, 60, 70],
  },
};

vi.mock("../api/queries", () => ({
  useIndicators: () => ({
    data: mockIndicatorsData,
    isLoading: false,
  }),
}));

vi.mock("../styles/ui", () => ({
  useColors: () => ({
    primary: "#087f98",
    accent: "#20c6e5",
    up: "#ec5d52",
    down: "#3ec98f",
    warning: "#f79009",
    border: "#203044",
    cardBg: "#101725",
    textPrimary: "#eef7fb",
    textSecondary: "#9cafbd",
    textMuted: "#627487",
  }),
}));

describe("IndicatorSubCharts", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders MACD by default and can switch to RSI and KDJ", () => {
    const handleTypeChange = vi.fn();
    render(
      <IndicatorSubCharts
        code="600519"
        types={["macd", "rsi", "kdj"]}
        onTypeChange={handleTypeChange}
      />,
    );

    expect(screen.getByText("MACD(12,26,9)")).toBeInTheDocument();
    expect(screen.getByText("DIF")).toBeInTheDocument();
    expect(screen.getByText("DEA")).toBeInTheDocument();

    fireEvent.click(screen.getByText("RSI(14)"));
    expect(handleTypeChange).toHaveBeenCalledWith("rsi");
    expect(screen.getAllByText("RSI(14)").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("┄ 70超买")).toBeInTheDocument();

    fireEvent.click(screen.getByText("KDJ(9,3,3)"));
    expect(handleTypeChange).toHaveBeenCalledWith("kdj");
    expect(screen.getByText("K")).toBeInTheDocument();
    expect(screen.getByText("D")).toBeInTheDocument();
    expect(screen.getByText("J")).toBeInTheDocument();
  });

  it("respects activeType prop directly", () => {
    const { rerender } = render(
      <IndicatorSubCharts
        code="600519"
        types={["macd", "rsi", "kdj"]}
        activeType="rsi"
      />,
    );

    expect(screen.getByText("┄ 70超买")).toBeInTheDocument();

    rerender(
      <IndicatorSubCharts
        code="600519"
        types={["macd", "rsi", "kdj"]}
        activeType="kdj"
      />,
    );

    expect(screen.getByText("K")).toBeInTheDocument();
    expect(screen.getByText("D")).toBeInTheDocument();
  });

  it("enables pressedMouseMove drag panning and updates indicator values on crosshair move", () => {
    render(
      <IndicatorSubCharts
        code="600519"
        types={["macd"]}
      />,
    );

    expect(mocks.createChart).toHaveBeenCalledWith(
      expect.any(HTMLElement),
      expect.objectContaining({
        handleScroll: expect.objectContaining({ pressedMouseMove: true }),
      }),
    );

    // Initial state shows latest values from mockIndicatorsData (index 2: 2026-09-12)
    expect(screen.getByText("2026-09-12")).toBeInTheDocument();
    expect(screen.getByText("0.70")).toBeInTheDocument(); // DIF
    expect(screen.getByText("0.50")).toBeInTheDocument(); // DEA
    expect(screen.getByText("+0.20")).toBeInTheDocument(); // MACD column

    // Crosshair hover on 2026-09-10 (index 0)
    const crosshairHandler = mocks.chart.subscribeCrosshairMove.mock.calls[0]?.[0];
    act(() => {
      crosshairHandler?.({
        time: { year: 2026, month: 9, day: 10 },
      });
    });

    expect(screen.getByText("2026-09-10")).toBeInTheDocument();
    expect(screen.getByText("0.50")).toBeInTheDocument(); // DIF
    expect(screen.getByText("0.40")).toBeInTheDocument(); // DEA
    expect(screen.getByText("+0.10")).toBeInTheDocument(); // MACD column
  });
});
