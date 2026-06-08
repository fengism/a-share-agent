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

export interface KlineItem {
  date: string;
  open: number;
  close: number;
  high: number;
  low: number;
  volume: number;
  amount: number;
  amplitude: number | null;
  turnover_pct: number | null;
  change_pct: number | null;
}

export interface KlineData {
  code: string;
  period: string;
  adjust: string;
  items: KlineItem[];
}

export interface IntradayItem {
  time: string;
  price: number;
  avg_price: number | null;
  volume: number | null;
  amount: number | null;
  change_pct: number | null;
}

export interface IntradayData {
  code: string;
  prev_close: number | null;
  items: IntradayItem[];
}

export interface FinancialMetrics {
  code: string;
  latest_report_date: string | null;
  metrics: Record<string, number | null>;
}

export interface FactorAnalysis {
  score: number;
  summary: string;
  strengths: string[];
  risks: string[];
  trend?: string;
  support_level?: number | null;
  resistance_level?: number | null;
  key_signals?: string[];
  market_mood?: string;
  heat_level?: string;
}

export interface AnalysisResult {
  stock_code: string;
  stock_name: string;
  analysis_date: string;
  current_price: number;
  fundamental: FactorAnalysis;
  technical: FactorAnalysis;
  sentiment: FactorAnalysis;
  valuation_view: string | null;
  fair_value_range: [number, number] | null;
  blended_fair_value: number | null;
  overall_rating: number;
  overall_summary: string;
  estimated_price_range: [number, number];
  signal: string;
  confidence: number;
  key_factors: string[];
  risk_warnings: string[];
}

export interface AnalysisHistoryItem {
  stock_code: string;
  stock_name: string;
  analysis_date: string;
  current_price: number | null;
  overall_rating: number | null;
  signal: string | null;
  confidence: number | null;
}

export interface TechnicalIndicators {
  ma: { ma5: number | null; ma10: number | null; ma20: number | null; ma60: number | null };
  macd: { dif: number | null; dea: number | null; macd_hist: number | null };
  rsi: number | null;
  boll: { upper: number | null; middle: number | null; lower: number | null };
  kdj: { k: number | null; d: number | null; j: number | null };
  volume_ma: { ma5: number | null; ma10: number | null };
  series: {
    dates: string[];
    ma5: (number | null)[];
    ma10: (number | null)[];
    ma20: (number | null)[];
    ma60: (number | null)[];
    dif: (number | null)[];
    dea: (number | null)[];
    macd_hist: (number | null)[];
    rsi: (number | null)[];
    boll_upper: (number | null)[];
    boll_middle: (number | null)[];
    boll_lower: (number | null)[];
    k: (number | null)[];
    d: (number | null)[];
    j: (number | null)[];
  };
}

export interface MarketIndices {
  indices: { code: string; name: string; price: number | null; change_pct: number | null; volume: number | null; amount: number | null }[];
  source?: string | null;
}

export interface HsgtFlowPoint {
  time: string;
  hgt: number | null;
  sgt: number | null;
  total: number | null;
}

export interface HsgtFlow {
  updated_at: string;
  unit: string;
  points: HsgtFlowPoint[];
}

export interface StockNews {
  title: string;
  content: string;
  source: string;
  time: string;
}

export interface CategorizedStockNews {
  code: string;
  eastmoney_news: StockNews[];
  cls_news: StockNews[];
}

export interface FeedNewsItem {
  title: string;
  content: string;
  source: string;
  publish_time: string;
  url: string;
  author: string;
  read_count: number;
  comment_count: number;
}

export interface RetailSentimentPost {
  text: string;
  author: string | null;
  publish_time: string | null;
}

export interface RetailSentiment {
  code: string;
  score: number | null;
  post_count: number;
  bullish_ratio: number | null;
  bearish_ratio: number | null;
  sample_posts: RetailSentimentPost[];
  summary: string;
  guba_post_count: number;
}

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

export interface StockSentiment {
  code: string;
  heat_score: number | null;
  hot_rank: number | null;
  news_count: number | null;
}

// Screener types
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
  industries?: string[] | null;
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
  second_industry: StockConcept | null;
}

export interface ScreenerResult {
  items: ScreenerItem[];
  total: number;
  page: number;
  page_size: number;
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

// Hot Rank types
export interface ThsHotStock {
  rank: number;
  code: string;
  name: string;
  change_pct: number;
  hot_value: number | null;
  concept_tag: string;
  pop_tag: string;
}

export interface ThsHotPlate {
  rank: number;
  code: string;
  name: string;
  change_pct: number;
  hot_value: number | null;
  hot_tag: string;
  tag: string;
}

// Dragon Tiger types
export interface DragonTigerItem {
  code: string;
  name: string;
  trade_date: string;
  close: number | null;
  change_pct: number | null;
  turnover_pct: number | null;
  net_amount: number | null;
  buy_amount: number | null;
  sell_amount: number | null;
  deal_amount: number | null;
  total_amount: number | null;
  net_amount_rate: number | null;
  deal_amount_rate: number | null;
  reason: string;
  explain: string;
  d1_chg: number | null;
  d2_chg: number | null;
  d5_chg: number | null;
}

export interface DragonTigerDetail {
  side: "buy" | "sell";
  code: string;
  operate_name: string;
  buy_amount: number | null;
  sell_amount: number | null;
  net_amount: number | null;
  buy_ratio: number | null;
  sell_ratio: number | null;
  reason: string;
}

export interface IndustryRankItem {
  rank: number;
  name: string;
  change_pct: number | null;
  code: string;
  up_count: number | null;
  down_count: number | null;
  leader: string;
  leader_change: number | null;
}

export interface IndustryRankings {
  sectors: IndustryRankItem[];
  total: number;
}

export interface NewsAnalysisRef {
  title: string;
  url: string;
}

export interface NewsAnalysisRef {
  title: string;
  url: string;
}

export interface NewsAnalysisItem {
  text: string;
  urls?: NewsAnalysisRef[];
}

export interface NewsAnalysisSection {
  title: string;
  icon: string;
  items: NewsAnalysisItem[];
}

export interface NewsAnalysis {
  market_sentiment: string;
  summary: string;
  sections: NewsAnalysisSection[];
}

export interface IndustryChainChart {
  title: string;
  description?: string;
  type: string;
  option: Record<string, unknown>;
}

export interface IndustryChainResult {
  name: string;
  summary: string;
  upstream: Record<string, unknown>[];
  midstream: Record<string, unknown>[];
  downstream: Record<string, unknown>[];
  drivers: string[];
  risks: string[];
  key_stocks: Record<string, unknown>[];
  llm_review: string;
  charts: IndustryChainChart[];
}

export interface IndustryChainHistoryItem {
  name: string;
  archive_id: string;
  saved_at: string;
  title: string;
  summary: string;
}

export interface NotionExportResponse {
  page_id: string;
  url: string;
  title: string;
}

export interface NotionDailyReviewExportRequest {
  date: string;
}

export interface NotionAnalysisExportRequest {
  code: string;
}

export interface PushRequest {
  target: "notion" | "feishu";
  type: "daily_review" | "analysis" | "chat" | "industry_chain";
  date?: string;
  code?: string;
  feishu_receiver?: string;
  chat_title?: string;
  chat_content?: string;
  industry_name?: string;
  archive_id?: string;
}

export interface PushResponse {
  success: boolean;
  target: string;
  url: string;
  title: string;
  message: string;
}

// Macro data types
export interface MacroIndicator {
  latest: Record<string, string | number | null> | null;
  trend: Record<string, string | number | null>[];
}

export interface MacroCategory {
  [indicatorKey: string]: MacroIndicator;
}

export interface MacroAllData {
  prices: MacroCategory;
  sentiment: MacroCategory;
  monetary: MacroCategory;
  rates: MacroCategory;
  growth: MacroCategory;
  trade: MacroCategory;
}
