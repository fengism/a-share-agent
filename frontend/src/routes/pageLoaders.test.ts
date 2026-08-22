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

  it("loads the Market route and prefetches its realtime overview", async () => {
    const loadMarket = vi.spyOn(pageLoaders, "market").mockResolvedValue({
      default: () => { throw new Error("preloaded page must not render in this test"); },
    });

    await preloadAppRoute("/market");

    expect(loadMarket).toHaveBeenCalledTimes(1);
    expect(prefetchMarketOverview).toHaveBeenCalledTimes(1);
  });
});
