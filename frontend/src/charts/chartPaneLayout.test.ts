import { describe, expect, it, vi } from "vitest";
import type { IChartApi } from "lightweight-charts";
import { applyVolumePaneLayout, getChartPaneThemeConfig, PRICE_PANE_RATIO } from "./chartPaneLayout";

describe("chartPaneLayout", () => {
  it("allocates stretch factor proportionally across price and volume panes", () => {
    const pane0 = { setStretchFactor: vi.fn(), setHeight: vi.fn() };
    const pane1 = { setStretchFactor: vi.fn(), setHeight: vi.fn() };
    const chart = {
      panes: vi.fn(() => [pane0, pane1]),
    } as unknown as IChartApi;

    applyVolumePaneLayout(chart);

    expect(pane0.setStretchFactor).toHaveBeenCalledWith(PRICE_PANE_RATIO);
    expect(pane1.setStretchFactor).toHaveBeenCalledWith(1 - PRICE_PANE_RATIO);
    expect(pane0.setHeight).not.toHaveBeenCalled();
    expect(pane1.setHeight).not.toHaveBeenCalled();
  });

  it("allocates custom stretch factor when provided", () => {
    const pane0 = { setStretchFactor: vi.fn(), setHeight: vi.fn() };
    const pane1 = { setStretchFactor: vi.fn(), setHeight: vi.fn() };
    const chart = {
      panes: vi.fn(() => [pane0, pane1]),
    } as unknown as IChartApi;

    applyVolumePaneLayout(chart, 0.65);

    expect(pane0.setStretchFactor).toHaveBeenCalledWith(0.65);
    expect(pane1.setStretchFactor).toHaveBeenCalledWith(0.35);
  });

  it("produces transparent native separator to prevent axis crossover and softened grid lines", () => {
    const mockThemeColors = {
      border: "#ded6c4",
      primary: "#b45309",
      accent: "#d97706",
    };

    const lightConfig = getChartPaneThemeConfig(mockThemeColors, true);
    expect(lightConfig.panes.enableResize).toBe(true);
    expect(lightConfig.panes.separatorColor).toBe("transparent");
    expect(lightConfig.panes.separatorHoverColor).toBe("transparent");
    expect(lightConfig.grid.horzLines.color).toContain("0.42");

    const darkConfig = getChartPaneThemeConfig(mockThemeColors, false);
    expect(darkConfig.panes.enableResize).toBe(true);
    expect(darkConfig.panes.separatorColor).toBe("transparent");
    expect(darkConfig.panes.separatorHoverColor).toBe("transparent");
    expect(darkConfig.grid.horzLines.color).toContain("0.45");
  });
});
