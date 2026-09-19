import type { KlineTradeMarker } from "../../charts/klineMarkers";
import type { PortfolioTransaction } from "../../types/portfolio";

const tradePriceFormatter = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});

function tradeDate(tradeTime: string): string | null {
  const date = tradeTime.slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(date) ? date : null;
}

export function filterPortfolioTransactions(
  transactions: PortfolioTransaction[],
  stockCode: string,
): PortfolioTransaction[] {
  return transactions
    .filter((transaction) => transaction.stock_code === stockCode)
    .sort((left, right) => (
      right.trade_time.localeCompare(left.trade_time) || right.id - left.id
    ));
}

export function buildPortfolioTradeMarkers(
  transactions: PortfolioTransaction[],
  stockCode: string,
): KlineTradeMarker[] {
  const grouped = new Map<string, {
    date: string;
    side: "buy" | "sell";
    transactions: PortfolioTransaction[];
  }>();

  for (const transaction of transactions) {
    if (transaction.stock_code !== stockCode) continue;
    const date = tradeDate(transaction.trade_time);
    if (!date) continue;
    const key = `${date}:${transaction.side}`;
    const current = grouped.get(key);
    if (current) current.transactions.push(transaction);
    else grouped.set(key, { date, side: transaction.side, transactions: [transaction] });
  }

  return [...grouped.values()]
    .sort((left, right) => (
      `${left.date}-${left.side}`.localeCompare(`${right.date}-${right.side}`)
    ))
    .map(({ date, side, transactions: matchingTransactions }) => ({
      date,
      side,
      label: matchingTransactions.length > 1
        ? `${side === "buy" ? "B" : "S"}×${matchingTransactions.length}`
        : `${side === "buy" ? "B" : "S"} ¥${tradePriceFormatter.format(matchingTransactions[0].trade_price)}`,
    }));
}

export function resolvePortfolioTradeDateRange(
  transactions: PortfolioTransaction[],
  stockCode: string,
  endDate: string,
): { startDate: string; endDate: string } | undefined {
  const dates = transactions
    .filter((transaction) => transaction.stock_code === stockCode)
    .map((transaction) => tradeDate(transaction.trade_time))
    .filter((date): date is string => Boolean(date))
    .sort();
  if (!dates.length) return undefined;
  return {
    startDate: dates[0].replace(/-/g, ""),
    endDate: endDate.replace(/-/g, ""),
  };
}
