export interface PotentialStockItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  market_cap: number | null;
  turnover_pct: number | null;
  amount: number | null;
  industry: string | null;
  strategies: string[];
  signal_types: string[];
  signal_date: string;
  signal_age_days: number | null;
  score: number;
  signal_score: number;
  quality_score: number;
  fundamental_score: number;
  theme_score: number;
  themes: string[];
  sector_strength: number | null;
  risk_flags: string[];
  reason: string;
}

export interface PotentialDailyResult {
  date: string;
  generated_at: string;
  universe_size: number;
  evaluated: number;
  failed_count: number;
  market_regime: "bull" | "bear" | "neutral";
  market_note: string | null;
  market_emotion: "strong" | "neutral" | "weak";
  advance_ratio: number | null;
  limit_up_count: number;
  limit_down_count: number;
  median_change_pct: number | null;
  hot_themes: string[];
  items: PotentialStockItem[];
}

export interface PotentialDateItem {
  date: string;
  count: number;
}

export interface PotentialPerformanceItem {
  code: string;
  name: string;
  industry: string | null;
  entry_price: number | null;
  exit_price: number | null;
  return_pct: number | null;
  benchmark_return_pct: number | null;
  excess_return_pct: number | null;
  max_return_pct: number | null;
  max_drawdown_pct: number | null;
}

export interface PotentialPerformanceSummary {
  date: string;
  days: number;
  generated_at: string;
  item_count: number;
  evaluated_count: number;
  win_rate: number | null;
  average_return_pct: number | null;
  median_return_pct: number | null;
  average_excess_pct: number | null;
  benchmark_return_pct: number | null;
  message: string | null;
  items: PotentialPerformanceItem[];
}

export interface PotentialRunStatus {
  running: boolean;
  status: string;
  date: string | null;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
}
