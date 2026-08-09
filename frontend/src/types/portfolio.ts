export interface PortfolioPositionCreate {
  stock_code: string;
  buy_price: number;
  buy_time: string;
  shares: number;
}

export interface PortfolioPosition {
  id: number;
  stock_code: string;
  stock_name: string;
  buy_price: number;
  buy_time: string;
  shares: number;
  current_price: number | null;
  change_pct: number | null;
  cost_value: number;
  market_value: number | null;
  profit_amount: number | null;
  profit_pct: number | null;
}

export interface PortfolioStockSummary {
  stock_code: string;
  stock_name: string;
  position_count: number;
  total_shares: number;
  average_cost: number;
  current_price: number | null;
  change_pct: number | null;
  cost_value: number;
  market_value: number | null;
  profit_amount: number | null;
  profit_pct: number | null;
}

export interface PortfolioSummary {
  stock_count: number;
  position_count: number;
  total_cost: number;
  priced_cost: number;
  total_market_value: number;
  total_profit_amount: number;
  total_profit_pct: number | null;
  profitable_count: number;
  losing_count: number;
  unpriced_count: number;
}

export interface PortfolioResponse {
  positions: PortfolioPosition[];
  stocks: PortfolioStockSummary[];
  summary: PortfolioSummary;
  quoted_at: string;
  quote_source: string;
  quote_stale: boolean;
}
