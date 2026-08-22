import { describe, expect, it } from "vitest";
import { QUERY_CACHE_POLICIES } from "./cachePolicies";

describe("query cache policies", () => {
  it("keeps realtime and THS cadences explicit", () => {
    expect(QUERY_CACHE_POLICIES.marketIndices).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.indexIntraday).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.stockIntraday).toEqual({ staleMs: 30_000, pollMs: 30_000 });
    expect(QUERY_CACHE_POLICIES.thsHotRank).toEqual({ staleMs: 300_000, pollMs: 300_000 });
  });
});
