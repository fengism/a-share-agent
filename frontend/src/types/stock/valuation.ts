export interface StockValuationPeer {
  name: string;
  code: string;
  pe_ttm: number | null;
  pb: number | null;
  ps_ttm: number | null;
}

export interface StockValuation {
  code: string;
  pe_ttm: number | null;
  pb: number | null;
  ps_ttm: number | null;
  peers: StockValuationPeer[];
}

export interface ValuationMultiples {
  pe_ttm: number | null;
  pb: number | null;
  ps_ttm: number | null;
  peg: number | null;
}

export interface ValuationPercentiles {
  pe_3y: number | null;
  pb_3y: number | null;
  ps_3y: number | null;
}

export interface ValuationFundamentals {
  revenue: number | null;
  revenue_yoy: number | null;
  net_profit: number | null;
  net_profit_yoy: number | null;
  non_net_profit: number | null;
  non_net_profit_yoy: number | null;
  shareholders_equity: number | null;
  operating_cashflow: number | null;
}

export interface ValuationProfile {
  category: string;
  label: string;
  rationale: string[];
}

export interface ValuationMethodResult {
  method: string;
  available: boolean;
  target_multiple: number | null;
  equity_value: number | null;
  per_share_value: number | null;
  upside_pct: number | null;
  confidence: string | null;
  confidence_score: number | null;
  weight: number | null;
  value_range: number[] | null;
  applicability: string | null;
  basis: string | null;
  reason: string | null;
}

export interface DCFValuationResult {
  method: string;
  available: boolean;
  base_cashflow: number | null;
  discount_rate: number | null;
  terminal_growth_rate: number | null;
  forecast_years: number;
  equity_value: number | null;
  per_share_value: number | null;
  upside_pct: number | null;
  confidence: string | null;
  confidence_score: number | null;
  weight: number | null;
  value_range: number[] | null;
  applicability: string | null;
  basis: string | null;
  reason: string | null;
}

export interface ValuationPeerSummary {
  pe_median: number | null;
  pb_median: number | null;
  ps_median: number | null;
  peer_count: number;
  peers: StockValuationPeer[];
}

export interface InstitutionForecast {
  metric: string;
  year: string;
  institution_count: number | null;
  min_value: number | null;
  mean_value: number | null;
  max_value: number | null;
  industry_avg: number | null;
  unit: string | null;
}

export interface StockValuationDetail {
  code: string;
  report_date: string | null;
  current_price: number | null;
  market_cap: number | null;
  total_shares: number | null;
  industry: string | null;
  multiples: ValuationMultiples;
  percentiles: ValuationPercentiles;
  fundamentals: ValuationFundamentals;
  peer_summary: ValuationPeerSummary;
  fair_values: Record<string, ValuationMethodResult | DCFValuationResult>;
  blended_fair_value: number | null;
  fair_value_range: number[] | null;
  valuation_view: string | null;
  valuation_summary: string | null;
  profile: ValuationProfile | null;
  method_weights: Record<string, number>;
  notes: string[];
  institution_forecasts: InstitutionForecast[];
}
