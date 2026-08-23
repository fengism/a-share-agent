export interface PotentialStockItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  market_cap: number | null;
  turnover_pct: number | null;
  amount: number | null;
  strategies: string[];
  signal_date: string;
  signal_age_days: number | null;
  score: number;
}

export interface PotentialDailyResult {
  date: string;
  generated_at: string;
  universe_size: number;
  evaluated: number;
  failed_count: number;
  items: PotentialStockItem[];
}

export interface PotentialDateItem {
  date: string;
  count: number;
}
