import { describe, expect, it, vi } from "vitest";
import { shouldFitChartContent } from "./chartLifecycle";

describe("shouldFitChartContent", () => {
  it("fits the first data view", () => {
    expect(shouldFitChartContent(null, "600519:daily:qfq")).toBe(true);
  });

  it("preserves the visible range for updates within the same view", () => {
    expect(shouldFitChartContent("600519:daily:qfq", "600519:daily:qfq")).toBe(false);
  });

  it("fits content when the stock, period, or indicator changes", () => {
    expect(shouldFitChartContent("600519:daily:qfq", "000001:daily:qfq")).toBe(true);
    expect(shouldFitChartContent("600519:daily:qfq", "600519:weekly:qfq")).toBe(true);
    expect(shouldFitChartContent("600519:macd", "600519:rsi")).toBe(true);
  });
});

describe("createDebouncedResizeHandler", () => {
  it("schedules resize callback via requestAnimationFrame", async () => {
    const { createDebouncedResizeHandler } = await import("./chartLifecycle");
    const onResize = vi.fn();
    const handler = createDebouncedResizeHandler(onResize);

    const mockEntry = { contentRect: { width: 400, height: 300 } } as ResizeObserverEntry;
    handler([mockEntry]);
    expect(onResize).not.toHaveBeenCalled();

    // Trigger rAF
    await new Promise((resolve) => requestAnimationFrame(resolve));
    expect(onResize).toHaveBeenCalledWith(mockEntry);
  });
});
