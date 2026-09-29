import type { ScreenerItem } from "../../types/stock";

export interface ExportCsvOptions {
  items: ScreenerItem[];
  strategySignalDates?: ReadonlyMap<string, string>;
  strategySignalAges?: ReadonlyMap<string, number>;
  strategyReturnsSinceSignal?: ReadonlyMap<string, number | null>;
  strategyAverageAmounts?: ReadonlyMap<string, number | null>;
  percentileMap?: ReadonlyMap<string, number | null>;
  showPercentile?: boolean;
}

function escapeCsvCell(cell: unknown): string {
  if (cell == null) return "";
  const str = String(cell);
  if (str.includes(",") || str.includes('"') || str.includes("\n") || str.includes("\r")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function generateScreenerCsv({
  items,
  strategySignalDates,
  strategySignalAges,
  strategyReturnsSinceSignal,
  strategyAverageAmounts,
  percentileMap,
  showPercentile,
}: ExportCsvOptions): string {
  const headers = [
    "代码",
    "名称",
    "市场",
    "现价",
    "涨跌幅(%)",
    "PE(TTM)",
    "PB",
    "总市值(亿)",
    "换手率(%)",
    "成交量",
    "申万行业",
    "概念题材",
    "交易所行业",
  ];

  const hasStrategy = Boolean(strategySignalDates?.size);
  if (hasStrategy) {
    headers.push("策略信号日", "信号年龄(根)", "信号后收益(%)", "20日均成交额(亿)");
  }
  if (showPercentile) {
    headers.push("PE分位(%)", "PB分位(%)");
  }

  const rows = items.map((item) => {
    const swIndustry = [item.first_industry?.name, item.second_industry?.name, item.third_industry?.name]
      .filter(Boolean)
      .join(" / ") || (item.second_industry?.name ?? item.first_industry?.name ?? "");
    const concepts = (item.concepts || []).join(" · ");

    const row: (string | number | null | undefined)[] = [
      item.code,
      item.name ?? "",
      item.board || item.exchange || "",
      item.price != null ? item.price.toFixed(2) : "",
      item.change_pct != null ? item.change_pct.toFixed(2) : "",
      item.pe_ttm != null ? item.pe_ttm.toFixed(2) : "",
      item.pb != null ? item.pb.toFixed(2) : "",
      item.market_cap != null ? item.market_cap.toFixed(2) : "",
      item.turnover_pct != null ? item.turnover_pct.toFixed(2) : "",
      item.volume != null ? item.volume : "",
      swIndustry,
      concepts,
      item.exchange_industry ?? "",
    ];

    if (hasStrategy) {
      const signalDate = strategySignalDates?.get(item.code) ?? "";
      const signalAge = strategySignalAges?.get(item.code);
      const ret = strategyReturnsSinceSignal?.get(item.code);
      const avgAmt = strategyAverageAmounts?.get(item.code);
      row.push(
        signalDate,
        signalAge != null ? signalAge : "",
        ret != null ? ret.toFixed(2) : "",
        avgAmt != null ? avgAmt.toFixed(2) : "",
      );
    }

    if (showPercentile) {
      const pePercentile = percentileMap?.get(item.code);
      const pbPercentile = percentileMap?.get(`${item.code}_pb`);
      row.push(
        pePercentile != null ? pePercentile.toFixed(0) : "",
        pbPercentile != null ? pbPercentile.toFixed(0) : "",
      );
    }

    return row.map(escapeCsvCell).join(",");
  });

  return "\uFEFF" + [headers.map(escapeCsvCell).join(","), ...rows].join("\r\n");
}

export function downloadScreenerCsv(options: ExportCsvOptions, filename?: string) {
  const dateStr = new Date().toISOString().slice(0, 10);
  const targetFilename = filename || `选股结果_${dateStr}.csv`;
  const csvContent = generateScreenerCsv(options);
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", targetFilename);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
