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
  amplitude_min?: number | null;
  amplitude_max?: number | null;
  volume_ratio_min?: number | null;
  volume_ratio_max?: number | null;
  change_pct_60d_min?: number | null;
  change_pct_60d_max?: number | null;
  is_broken_net?: boolean;
  exclude_st?: boolean;
  min_listing_days?: number | null;
  min_amount_yi?: number | null;
  industries?: string[] | null;
  concepts?: string[] | null;
  markets?: string[] | null;
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
  amplitude?: number | null;
  volume_ratio?: number | null;
  change_pct_60d?: number | null;
  composite_score?: number | null;
  is_broken_net?: boolean;
  exchange?: string | null;
  board?: string | null;
  listing_date?: string | null;
  exchange_industry?: string | null;
  first_industry?: StockConcept | null;
  second_industry: StockConcept | null;
  third_industry?: StockConcept | null;
  concepts?: string[];
}

export interface ScreenerPreset {
  key: string;
  name: string;
  category: "value" | "theme" | "growth" | string;
  description: string;
  filters: ScreenerFilter;
}

export interface ScreenerResult {
  items: ScreenerItem[];
  total: number;
  page: number;
  page_size: number;
  sw_industry_coverage?: number;
  exchange_industry_coverage?: number;
  stock_master_complete?: boolean;
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

export interface ScreenerStrategyParameter {
  key: string;
  type: string;
  label: string;
  description: string;
  default: number | boolean | string;
  minimum?: number | null;
  maximum?: number | null;
  step?: number | null;
}

export interface ScreenerStrategyPreset {
  key: string;
  name: string;
  description: string;
  scenario: string;
  risk_level: string;
  parameters: Record<string, number | boolean | string>;
  parameter_definitions: ScreenerStrategyParameter[];
}

export interface ScreenerStrategyRequest {
  strategy_key: string;
  version?: string | null;
  parameters?: Record<string, number | boolean | string>;
  codes: string[];
  lookback_days?: number;
  max_signal_age_bars?: number | null;
}

export interface ScreenerStrategyMatch {
  code: string;
  signal_date: string;
  target_position: number;
  signal_age_bars: number;
  entry_price: number | null;
  latest_price: number | null;
  return_since_signal_pct: number | null;
  average_amount_20d_yi: number | null;
  data_source?: string;
  data_hash?: string;
  used_fallback?: boolean;
}

export interface ScreenerStrategyResult {
  strategy_key: string;
  strategy_name: string;
  strategy_version: string;
  definition_hash: string;
  parameters: Record<string, number | boolean | string>;
  matches: ScreenerStrategyMatch[];
  matched_codes: string[];
  evaluated: number;
  failed: Record<string, string>;
  excluded: Record<string, string>;
  fallback_count?: number;
}
