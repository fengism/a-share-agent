import type { QuantBacktestResult } from "../../../api/queries";
import type { KlineTradeMarker } from "../../../charts/klineMarkers";

export function buildBacktestTradeMarkers(
  trades: QuantBacktestResult["trades"],
  code: string,
): KlineTradeMarker[] {
  const grouped = new Map<string, { date: string; side: "buy" | "sell"; count: number }>();
  for (const trade of trades) {
    if (trade.code !== code) continue;
    const key = `${trade.date}:${trade.side}`;
    const current = grouped.get(key);
    if (current) current.count += 1;
    else grouped.set(key, { date: trade.date, side: trade.side, count: 1 });
  }
  return [...grouped.values()]
    .sort((left, right) => `${left.date}-${left.side}`.localeCompare(`${right.date}-${right.side}`))
    .map((item) => ({
      date: item.date,
      side: item.side,
      label: `${item.side === "buy" ? "买" : "卖"}${item.count > 1 ? `×${item.count}` : ""}`,
    }));
}

export function resolveBacktestTradeCodes(
  codes: QuantBacktestResult["codes"],
  trades: QuantBacktestResult["trades"],
): string[] {
  const traded = new Set(trades.map((trade) => trade.code));
  return [...new Set([...codes.filter((code) => traded.has(code)), ...traded])];
}

export function resolveBacktestDateRange(
  equityCurve: QuantBacktestResult["equity_curve"],
  trades: QuantBacktestResult["trades"],
): { startDate: string; endDate: string } | undefined {
  const dates = [
    ...equityCurve.map((point) => point.date),
    ...trades.map((trade) => trade.date),
  ].filter(Boolean).sort();
  if (!dates.length) return undefined;
  return {
    startDate: dates[0].replace(/-/g, ""),
    endDate: dates[dates.length - 1].replace(/-/g, ""),
  };
}
