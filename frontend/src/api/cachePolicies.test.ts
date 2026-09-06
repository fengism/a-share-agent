import { describe, expect, it } from "vitest";
import { QUERY_CACHE_POLICIES } from "./cachePolicies";

describe("query cache policies", () => {
  it("defines shared policies for market, macro, reference, and historical data", () => {
    expect(QUERY_CACHE_POLICIES.marketRealtime).toEqual({ staleMs: 60_000, pollMs: 60_000 });
    expect(QUERY_CACHE_POLICIES.marketMinute).toEqual({ staleMs: 300_000, pollMs: 300_000 });
    expect(QUERY_CACHE_POLICIES.marketTenMinutes).toEqual({ staleMs: 600_000 });
    expect(QUERY_CACHE_POLICIES.marketThirtyMinutes).toEqual({ staleMs: 1_800_000 });
    expect(QUERY_CACHE_POLICIES.marketDaily).toEqual({ staleMs: 86_400_000 });
    expect(QUERY_CACHE_POLICIES.macro).toEqual({ staleMs: 3_600_000 });
    expect(QUERY_CACHE_POLICIES.reference).toEqual({ staleMs: 86_400_000 });
    expect(QUERY_CACHE_POLICIES.immutableHistory).toEqual({ staleMs: 86_400_000 });
    expect(QUERY_CACHE_POLICIES.priceAnomaly).toEqual({ staleMs: 86_400_000 });
  });

  it("keeps feature-specific refresh and retention policies explicit", () => {
    expect(QUERY_CACHE_POLICIES.socialFeed).toEqual({
      staleMs: 1_800_000,
      pollMs: 1_800_000,
    });
    expect(QUERY_CACHE_POLICIES.socialAnalysis).toEqual({
      staleMs: 43_200_000,
      gcMs: 43_200_000,
    });
    expect(QUERY_CACHE_POLICIES.portfolioRealtime).toEqual({ staleMs: 15_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.watchlistRealtime).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.hkStockSearch).toEqual({ staleMs: 300_000, gcMs: 1_800_000 });
    expect(QUERY_CACHE_POLICIES.capabilitiesCatalog).toEqual({ staleMs: 300_000 });
    expect(QUERY_CACHE_POLICIES.capabilitiesAvailability).toEqual({ staleMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.potentialResults).toEqual({ staleMs: 600_000 });
    expect(QUERY_CACHE_POLICIES.screenerResults).toEqual({ staleMs: 120_000 });
  });

  it("keeps realtime and THS cadences explicit", () => {
    expect(QUERY_CACHE_POLICIES.marketIndices).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.indexIntraday).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.stockIntraday).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.thsHotRank).toEqual({ staleMs: 300_000, pollMs: 300_000 });
  });

  it("centralizes application and settings defaults without changing their cadence", () => {
    expect(QUERY_CACHE_POLICIES.defaultQuery).toEqual({ staleMs: 60_000 });
    expect(QUERY_CACHE_POLICIES.settingsConfig).toEqual({ staleMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.settingsBotJobs).toEqual({ staleMs: 10_000 });
    expect(QUERY_CACHE_POLICIES.settingsInvites).toEqual({ staleMs: 30_000 });
  });

  it("keeps workflow state polling separate from cache freshness", () => {
    expect(QUERY_CACHE_POLICIES.workflowActive).toEqual({
      staleMs: 1_000,
      activePollMs: 2_000,
      idlePollMs: 10_000,
    });
    expect(QUERY_CACHE_POLICIES.workflowHistory).toEqual({ staleMs: 300_000 });
    expect(QUERY_CACHE_POLICIES.workflowImmutableSnapshot).toEqual({
      staleMs: Number.POSITIVE_INFINITY,
    });
    expect(QUERY_CACHE_POLICIES.workflowLatest).toEqual({ staleMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.workflowAtlas).toEqual({ staleMs: 300_000 });
  });

  it("keeps quant job polling semantics explicit", () => {
    expect(QUERY_CACHE_POLICIES.quantPresets).toEqual({
      staleMs: 60_000,
      pollMs: 600_000,
    });
    expect(QUERY_CACHE_POLICIES.quantDrafts).toEqual({ activePollMs: 1_000 });
    expect(QUERY_CACHE_POLICIES.quantBacktestRuns).toEqual({
      listActivePollMs: 2_000,
      detailActivePollMs: 1_000,
    });
  });
});
