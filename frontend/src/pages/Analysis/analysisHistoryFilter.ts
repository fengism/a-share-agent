import type { AnalysisHistoryItem } from "../../types/stock";

export function filterAnalysisHistory(items: AnalysisHistoryItem[], query: string) {
  const keyword = query.trim().toLocaleLowerCase();
  if (!keyword) return items;
  return items.filter((item) => (
    item.stock_code.toLocaleLowerCase().includes(keyword)
    || item.stock_name.toLocaleLowerCase().includes(keyword)
  ));
}
