import type { UTCTimestamp } from "lightweight-charts";

export interface IntradayVisibleRange {
  from: UTCTimestamp;
  to: UTCTimestamp;
}

export function buildIntradayVisibleRange(timestamp: number): IntradayVisibleRange | null {
  if (!Number.isFinite(timestamp)) return null;
  const date = new Date(timestamp * 1000);
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  return {
    from: Date.UTC(year, month, day, 9, 0) / 1000 as UTCTimestamp,
    to: Date.UTC(year, month, day, 16, 0) / 1000 as UTCTimestamp,
  };
}
