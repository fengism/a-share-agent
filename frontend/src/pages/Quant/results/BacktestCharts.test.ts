import { describe, expect, it } from "vitest";
import { buildDrawdownChartOption, buildEquityChartOption } from "./backtestChartOptions";

const colors = {
  border: "#ddd",
  down: "#00aa66",
  primary: "#1677ff",
  textMuted: "#999",
  textSecondary: "#666",
};
const curve = [
  { date: "2026-01-01", equity: 1, benchmark: 1, drawdown: 0 },
  { date: "2026-01-02", equity: 1.02, benchmark: 1.01, drawdown: -0.01 },
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
});
