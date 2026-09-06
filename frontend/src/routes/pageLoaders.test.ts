import { beforeEach, describe, expect, it, vi } from "vitest";

const { prefetchMarketOverview } = vi.hoisted(() => ({
  prefetchMarketOverview: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../pages/Market/prefetch", () => ({ prefetchMarketOverview }));

import { pageLoaders, preloadAppRoute } from "./pageLoaders";

describe("preloadAppRoute", () => {
  beforeEach(() => {
    prefetchMarketOverview.mockClear();
  });

  it("loads the investment research page for a dynamic stock route", async () => {
    const loadInvestmentResearch = vi.spyOn(pageLoaders, "investmentResearch").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/investment-research/600519");

    expect(loadInvestmentResearch).toHaveBeenCalledTimes(1);
  });

  it("loads the stock facts page for a dynamic stock route", async () => {
    const loadStock = vi.spyOn(pageLoaders, "stock").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/stock/600519");

    expect(loadStock).toHaveBeenCalledTimes(1);
  });

  it("loads the dashboard and prefetches the merged market overview", async () => {
    const loadDashboard = vi.spyOn(pageLoaders, "dashboard").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/");

    expect(loadDashboard).toHaveBeenCalledTimes(1);
    expect(prefetchMarketOverview).toHaveBeenCalledTimes(1);
  });

  it("preloads the unified feed for the legacy Twitter route", async () => {
    const loadFeed = vi.spyOn(pageLoaders, "feed").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/twitter");

    expect(loadFeed).toHaveBeenCalledTimes(1);
  });

  it("preloads the standalone trading calendar route", async () => {
    const loadTradingCalendar = vi.spyOn(pageLoaders, "tradingCalendar").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/trading-calendar");

    expect(loadTradingCalendar).toHaveBeenCalledTimes(1);
  });

  it("preloads the Hong Kong market route", async () => {
    const loadHKMarket = vi.spyOn(pageLoaders, "hkMarket").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/hk-market");

    expect(loadHKMarket).toHaveBeenCalledTimes(1);
  });

  it("preloads the industry classification route", async () => {
    const loadIndustryClassification = vi.spyOn(pageLoaders, "industryClassification").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/industry-classification");

    expect(loadIndustryClassification).toHaveBeenCalledTimes(1);
  });

  it("loads the Market route without prefetching the homepage overview", async () => {
    const loadMarket = vi.spyOn(pageLoaders, "market").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/market");

    expect(loadMarket).toHaveBeenCalledTimes(1);
    expect(prefetchMarketOverview).not.toHaveBeenCalled();
  });
});
