export interface StockCompareItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  pe_ttm: number | null;
  pb: number | null;
  ps_ttm: number | null;
  market_cap: number | null;
  turnover_pct: number | null;
  industry: string | null;
  revenue: number | null;
  net_profit: number | null;
  roe: number | null;
}
