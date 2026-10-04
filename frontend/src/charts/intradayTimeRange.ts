import type { UTCTimestamp } from "lightweight-charts";

export interface IntradayVisibleRange {
  from: UTCTimestamp;
  to: UTCTimestamp;
}

export function buildIntradayVisibleRange(
  timestamp: number,
  market: "cn" | "hk" = "cn",
): IntradayVisibleRange | null {
  if (!Number.isFinite(timestamp)) return null;
  const date = new Date(timestamp * 1000);
  const year = date.getUTCFullYear();
  const month = date.getUTCMonth();
  const day = date.getUTCDate();
  const endHour = market === "hk" ? 16 : 15;
  return {
    from: (Date.UTC(year, month, day, 9, 30) / 1000) as UTCTimestamp,
    to: (Date.UTC(year, month, day, endHour, 0) / 1000) as UTCTimestamp,
  };
}
