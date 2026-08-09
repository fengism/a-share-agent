import { describe, expect, it } from "vitest";
import {
  DEFAULT_SCREENER_FILTERS,
  parseScreenerUrlState,
  serializeScreenerUrlState,
} from "./screenerUrlState";

describe("screener URL state", () => {
  it("round-trips applied filters and percentile settings", () => {
    const state = parseScreenerUrlState(new URLSearchParams(
      "pe_max=15&market_cap_min=200&industries=银行,保险&sort=pe&order=asc&page=2&size=20&percentile=1&pe_pct=30",
    ));

    expect(state).toMatchObject({
      filters: {
        pe_max: 15,
        market_cap_min: 200,
        industries: ["银行", "保险"],
        sort_by: "pe",
        sort_order: "asc",
        page: 2,
        page_size: 20,
      },
      showPercentile: true,
      pePercentileMax: 30,
      pbPercentileMax: 50,
    });
    expect(parseScreenerUrlState(serializeScreenerUrlState(state))).toEqual(state);
  });

  it("falls back for invalid sort, page and percentile values", () => {
    const state = parseScreenerUrlState(new URLSearchParams("sort=unknown&page=-1&size=bad&pe_pct=200"));
    expect(state.filters).toEqual(DEFAULT_SCREENER_FILTERS);
    expect(state.pePercentileMax).toBe(100);
  });

  it("omits default values from the URL", () => {
    const params = serializeScreenerUrlState({
      filters: DEFAULT_SCREENER_FILTERS,
      showPercentile: false,
      pePercentileMax: 50,
      pbPercentileMax: 50,
    });
    expect(params.toString()).toBe("");
  });
});
