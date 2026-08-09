import type { StockConcept } from "./profile";

export interface ScreenerFilter {
  pe_min?: number | null;
  pe_max?: number | null;
  pb_min?: number | null;
  pb_max?: number | null;
  price_min?: number | null;
  price_max?: number | null;
  market_cap_min?: number | null;
  market_cap_max?: number | null;
  change_pct_min?: number | null;
  change_pct_max?: number | null;
  turnover_pct_min?: number | null;
  turnover_pct_max?: number | null;
  industries?: string[] | null;
  sort_by: string;
  sort_order: "asc" | "desc";
  page: number;
  page_size: number;
}

export interface ScreenerItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  pe_ttm: number | null;
  pb: number | null;
  market_cap: number | null;
  turnover_pct: number | null;
  volume: number | null;
  second_industry: StockConcept | null;
}

export interface ScreenerResult {
  items: ScreenerItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface ValuationPercentileRequest {
  codes: string[];
  period: string;
  indicator: string;
}

export interface ValuationPercentileItem {
  code: string;
  percentile: number | null;
}

export interface ValuationPercentileResult {
  items: ValuationPercentileItem[];
}
