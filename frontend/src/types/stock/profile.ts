export interface StockSearchItem {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
}

export interface StockConcept {
  code: string;
  name: string;
}

export interface StockBasicInfo {
  code: string;
  name: string;
  listing_date: string | null;
  total_shares: number | null;
  circulating_shares: number | null;
  pe_ttm: number | null;
  pb: number | null;
  market_cap: number | null;
  turnover_pct: number | null;
  first_industry: StockConcept | null;
  second_industry: StockConcept | null;
}
