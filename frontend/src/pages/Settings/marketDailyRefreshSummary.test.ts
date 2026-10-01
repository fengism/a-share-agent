import { describe, expect, it } from "vitest";
import type { MarketDailyBarRefreshResult } from "../../types/settings";
import { summarizeRefreshResult } from "./marketDailyRefreshSummary";

function status(segment: "cn_stock" | "hk_stock", value: "success" | "failed") {
  return {
    trade_date: "2026-09-30",
    checkpoint: "recheck" as const,
    segment,
    status: value,
    attempts: 1,
    next_retry_at: null,
    expected_count: null,
    stored_count: null,
    last_error: value === "failed" ? "offline" : null,
    started_at: null,
    completed_at: null,
  };
}

describe("summarizeRefreshResult", () => {
  it("only summarizes requested segments for the requested phase", () => {
    const result: MarketDailyBarRefreshResult = {
      trade_date: "2026-09-30",
      checkpoint: "recheck",
      requested_segments: ["cn_stock", "hk_stock"],
      statuses: [status("cn_stock", "success"), status("hk_stock", "failed")],
    };

    expect(summarizeRefreshResult(result)).toEqual({
      total: 2,
      success: 1,
      skipped: 0,
      failed: 1,
    });
  });
});
