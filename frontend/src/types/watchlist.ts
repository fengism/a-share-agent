export type WatchlistAlertCondition =
  | "price_above"
  | "price_below"
  | "change_pct_above"
  | "change_pct_below";

export interface WatchlistAlertCreate {
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
  note: string;
}

export interface WatchlistItem {
  id: number;
  stock_code: string;
  stock_name: string;
  note: string;
  created_at: string;
  current_price: number | null;
  change_pct: number | null;
  quote_source: string;
  alerts: WatchlistAlert[];
}

export interface WatchlistResponse {
  items: WatchlistItem[];
  source: string;
  quoted_at: string;
}
