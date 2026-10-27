import { describe, expect, it } from "vitest";
import {
  buildAlphaRiskChartOption,
  buildDrawdownChartOption,
  buildEquityChartOption,
  buildHoldingsAllocationChartOption,
} from "./backtestChartOptions";

const colors = {
  border: "#ddd",
  down: "#00aa66",
  primary: "#1677ff",
  textMuted: "#999",
  textSecondary: "#666",
};
const curve = [
  {
    date: "2026-01-01",
    equity: 1,
    benchmark: 1,
    drawdown: 0,
    cash: 0.5,
    positions_value: 0.5,
    position_weights: { CASH: 0.5, "600519": 0.5 },
    excess_return: 0,
    rolling_sharpe: 1.5,
    rolling_beta: 0.9,
  },
  {
    date: "2026-01-02",
    equity: 1.02,
    benchmark: 1.01,
    drawdown: -0.01,
    cash: 0.4,
    positions_value: 0.62,
    position_weights: { CASH: 0.4, "600519": 0.62 },
    excess_return: 1.0,
    rolling_sharpe: 1.6,
    rolling_beta: 0.95,
  },
];

describe("buildEquityChartOption", () => {
  it("keeps the legend centered above a contain-label plot grid", () => {
    const option = buildEquityChartOption(curve, colors, false);

    expect(option.legend).toMatchObject({ left: "center", top: 4, itemGap: 20 });
    expect(option.grid).toMatchObject({ top: 58, containLabel: true });
    expect(option.grid.top).toBeGreaterThan(option.legend.top + 40);
    expect(option.xAxis.axisLabel.margin).toBe(12);
    expect(option.yAxis.axisLabel.margin).toBe(10);
  });

  it("reserves additional top space and shortens dates on narrow screens", () => {
    const option = buildEquityChartOption(curve, colors, true);

    expect(option.legend).toMatchObject({ left: "center", top: 6, itemGap: 12 });
    expect(option.grid).toMatchObject({ top: 62, containLabel: true });
    expect(option.grid.left).toBe(12);
    expect(option.grid.right).toBe(12);
    expect(option.xAxis.axisLabel.formatter("2026-01-02")).toBe("01-02");
    expect(option.yAxis.axisLabel.formatter(1.2345)).toBe("1.23");
    expect(option.tooltip.valueFormatter(1.23456)).toBe("1.2346");
  });

  it("formats drawdown values and keeps axes inside the grid", () => {
    const option = buildDrawdownChartOption(curve, colors, false);

    expect(option.grid.containLabel).toBe(true);
    expect(option.xAxis.boundaryGap).toBe(false);
    expect(option.yAxis.axisLabel.formatter(-3.1415)).toBe("-3.1%");
    expect(option.tooltip.valueFormatter(-3.1415)).toBe("-3.14%");
    expect(option.series[0].data).toEqual([0, -1]);
  });

  it("builds holdings allocation chart option with stacked series", () => {
    const option = buildHoldingsAllocationChartOption(curve, colors, false);

    expect(option.grid.containLabel).toBe(true);
    expect(option.series.length).toBe(2);
    expect(option.series[0].name).toBe("现金 (CASH)");
    expect(option.series[0].stack).toBe("Total");
    expect(option.series[0].data).toEqual([50, 40]);
    expect(option.series[1].name).toBe("600519");
    expect(option.series[1].data).toEqual([50, 62]);
  });

  it("builds alpha and rolling risk chart option with dual y-axes", () => {
    const option = buildAlphaRiskChartOption(curve, colors, false);

    expect(option.yAxis.length).toBe(2);
    expect(option.series.length).toBe(3);
    expect(option.series[0].name).toBe("超额收益 (Alpha)");
    expect(option.series[0].data).toEqual([0, 1.0]);
    expect(option.series[1].name).toBe("60日滚动夏普");
    expect(option.series[1].data).toEqual([1.5, 1.6]);
    expect(option.series[2].name).toBe("60日滚动贝塔");
    expect(option.series[2].data).toEqual([0.9, 0.95]);
  });
});
