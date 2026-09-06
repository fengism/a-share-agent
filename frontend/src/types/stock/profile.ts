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

export interface StockDataSource {
  id: string;
  name: string;
  provider: string;
  operation: string;
  api: string;
}

export interface StockBasicInfo {
  code: string;
  name: string;
  listing_date: string | null;
  total_shares: number | null;
  circulating_shares: number | null;
  pe_ttm: number | null;
  pe_static: number | null;
  pb: number | null;
  market_cap: number | null;
  float_market_cap: number | null;
  turnover_pct: number | null;
  exchange_industry?: string | null;
  first_industry: StockConcept | null;
  second_industry: StockConcept | null;
  third_industry?: StockConcept | null;
  current_price: number | null;
  concepts: StockConcept[] | null;
  data_sources?: StockDataSource[];
  field_sources?: Record<string, string>;
}

export interface StockBusinessIntro {
  code: string;
  source: string;
  items: Record<string, string>;
}
