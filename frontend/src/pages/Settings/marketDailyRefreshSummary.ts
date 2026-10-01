import type { MarketDailyBarRefreshResult } from "../../types/settings";

export function summarizeRefreshResult(result: MarketDailyBarRefreshResult) {
  const requested = new Set(result.requested_segments);
  const statuses = result.statuses.filter(
    (item) => item.trade_date === result.trade_date
      && item.checkpoint === result.checkpoint
      && requested.has(item.segment),
  );
  return {
    total: result.requested_segments.length,
    success: statuses.filter((item) => item.status === "success").length,
    skipped: statuses.filter((item) => item.status === "skipped").length,
    failed: statuses.filter((item) => item.status === "failed").length,
  };
}
