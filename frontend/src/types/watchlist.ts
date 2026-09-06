export type WatchlistMarket = "cn" | "hk";

export type WatchlistAlertCondition =
  | "price_above"
  | "price_below"
  | "change_pct_above"
  | "change_pct_below";

export interface WatchlistAlertCreate {
  market?: WatchlistMarket;
  condition: WatchlistAlertCondition;
  threshold: number;
}

export interface WatchlistAlert extends WatchlistAlertCreate {
  id: number;
  stock_code: string;
  enabled: boolean;
  triggered: boolean;
  current_value: number | null;
  created_at: string;
}

export interface WatchlistItemCreate {
  stock_code: string;
  market?: WatchlistMarket;
  note: string;
}

export interface WatchlistConcept {
  code: string;
  name: string;
}

export interface WatchlistItem {
  id: number;
  stock_code: string;
  market?: WatchlistMarket;
  stock_name: string;
  note: string;
  created_at: string;
  current_price: number | null;
  change_pct: number | null;
  open_price: number | null;
  high_price: number | null;
  low_price: number | null;
  previous_close: number | null;
  volume: number | null;
  amount: number | null;
  turnover_pct: number | null;
  pe_ttm: number | null;
  market_cap: number | null;
  quote_source: string;
  concepts: WatchlistConcept[];
  alerts: WatchlistAlert[];
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  source: string;
  quoted_at: string;
}
