import type { components } from "../../api/generated/schema";
import type { IntradayItem } from "./quotes";

export interface MarketIndices {
  indices: {
    code: string;
    name: string;
    price: number | null;
    change_pct: number | null;
    volume: number | null;
    amount: number | null;
    pre_close?: number | null;
  }[];
  source?: string | null;
}

export interface IndexIntradayData {
  code: string;
  source: string;
  prev_close: number | null;
  items: IntradayItem[];
}

export interface HsgtFlowPoint {
  time: string;
  hgt: number | null;
  sgt: number | null;
  total: number | null;
}

export interface HsgtFlow {
  date: string;
  updated_at: string;
  unit: string;
  is_stale: boolean;
  points: HsgtFlowPoint[];
}

export interface NorthboundHistoryPoint {
  date: string;
  north_money: number | null;
  sh_connect: number | null;
  sz_connect: number | null;
  south_money: number | null;
  hs300_open: number | null;
  hs300_close: number | null;
  hs300_high: number | null;
  hs300_low: number | null;
  hs300_change: number | null;
  hs300_change_pct: number | null;
}

export interface NorthboundHistory {
  source: "乐咕乐股" | "东方财富";
  updated_at: string;
  unit: string;
  index_name: string;
  is_stale: boolean;
  items: NorthboundHistoryPoint[];
}

export interface MarketEmotionDistribution {
  status: boolean;
  suspend_num: number;
  up_num: number;
  down_num: number;
  rise_num: number;
  fall_num: number;
  flat_num: number;
  down_10: number;
  down_8: number;
  down_6: number;
  down_4: number;
  down_2: number;
  up_2: number;
  up_4: number;
  up_6: number;
  up_8: number;
  up_10: number;
}

export interface MarketLimitUpBoardItem {
  name: string;
  count: number;
  promotion_rate: string | null;
}

export interface MarketEmotion {
  source: "财联社" | "fuyao";
  fetched_at: string;
  market_degree: number | null;
  shsz_balance: string;
  shsz_balance_change_px: string;
  preview_balance: string;
  preview_balance_change_px: string;
  up_ratio: string;
  up_ratio_num: number | null;
  up_open_num: number | null;
  performance: string;
  up_open_ratio: string;
  profit_ratio: string;
  up_down_dis: MarketEmotionDistribution;
  limit_up_board: MarketLimitUpBoardItem[];
}

export interface MarketLimitUpLadderStock {
  code: string;
  name: string;
  board_count: number;
  limit_up_time: string;
  sector_code: string;
  sector_name: string;
  one_word: boolean;
  popular: boolean;
  sector_limit_up_count: number;
  amount: number;
  sector_amount: number;
}

export interface MarketLimitUpLadderSector {
  sector_code: string;
  sector_name: string;
  stock_count: number;
  amount: number;
  stock_codes: string[];
}

export interface MarketLimitUpLadder {
  source: "开盘红" | "fuyao";
  date: string;
  fetched_at: string;
  total: number;
  stocks: MarketLimitUpLadderStock[];
  sectors: MarketLimitUpLadderSector[];
}

export type MarketLimitHistoryCategory = "limit_up" | "limit_down" | "wind_vane";

export interface MarketLimitHistoryItem {
  code: string;
  name: string;
  limit_time: string;
  open_time: string;
  seal_amount: number;
  limit_tag: string;
  limit_count: number;
  themes: string;
  net_inflow: number;
  turnover: number;
  turnover_rate: number | null;
  market_cap: number;
  reason: string;
  seal_money: number;
  industry_id: string;
  industry_limit_up_count: number;
}

export interface MarketLimitHistory {
  source: "开盘红" | "fuyao";
  date: string;
  category: MarketLimitHistoryCategory;
  fetched_at: string;
  total: number;
  items: MarketLimitHistoryItem[];
}

export interface MarketSectorStocksHistoryItem {
  code: string;
  name: string;
  tags: string;
  price: number | null;
  change_pct: number | null;
  amount: number | null;
  turnover_rate: number | null;
  float_amount: number | null;
  main_buy: number | null;
  main_sell: number | null;
  main_net: number | null;
  buy_ratio: number | null;
  sell_ratio: number | null;
  net_ratio: number | null;
  limit_tag: string;
  rank_tag: string;
  recent_chg: number | null;
  limit_count: number | null;
  chg_1d: number | null;
  chg_5d: number | null;
  chg_20d: number | null;
  quote_source: string | null;
  quoted_at: string | null;
}

export interface MarketSectorStocksHistory {
  source: "开盘红";
  date: string;
  constituent_date: string;
  plate_id: string;
  fetched_at: string;
  quoted_at: string | null;
  quote_source: string | null;
  is_realtime: boolean;
  realtime_partial: boolean;
  history_details_available: boolean;
  total: number;
  items: MarketSectorStocksHistoryItem[];
}

export interface MarketWindPlate {
  plate_code: string;
  plate_name: string;
  catalyst: string;
}

export interface MarketMainlineFaucetStock {
  code: string;
  name: string;
  change_pct: number | null;
  reason: string;
}

export interface MarketMainlinePlate {
  code: string;
  name: string;
  reason: string;
  rise_count: number | null;
  change_pct: number | null;
  article_title: string;
  faucets: MarketMainlineFaucetStock[];
}

export interface MarketMainlineChance {
  title: string;
  description: string;
  continued_days: number | null;
  hot: number | null;
  plates: MarketMainlinePlate[];
}

export interface MarketMainlineStyleIndexStock {
  code: string;
  name: string;
  change_30d: number | null;
}

export interface MarketMainlineStyleIndex {
  code: string;
  name: string;
  change_30d: number | null;
  stocks: MarketMainlineStyleIndexStock[];
}

export interface MarketMainlineStyle {
  title: string;
  interpret: string;
  indexes: MarketMainlineStyleIndex[];
}

export interface MarketMainline {
  source: "财联社";
  fetched_at: string;
  style: MarketMainlineStyle | null;
  items: MarketMainlineChance[];
}

export interface MarketWind {
  source: "财联社";
  fetched_at: string;
  items: MarketWindPlate[];
}

export interface MarketMarginItem {
  date: string;
  rzye: number | null;
  rqye: number | null;
  rzrqye: number | null;
  rzmre: number | null;
  rzche: number | null;
  rzjme: number | null;
}

export interface MarketMargin {
  source: "东方财富";
  fetched_at: string;
  items: MarketMarginItem[];
}
export interface MarketBreadthDailySummary {
  date: string;
  strong_industry_count: number;
  total_industry_count: number;
  strong_ratio: number;
}

export interface MarketBreadth {
  source: "本地计算";
  fetched_at: string;
  industries: string[];
  dates: string[];
  values: (number | null)[][];
  summaries: MarketBreadthDailySummary[];
}

export type MarketPriceAnomalyExchange = "SH" | "SZ" | "BJ";

export interface MarketPriceAnomalyItem {
  code: string;
  name: string;
  market: MarketPriceAnomalyExchange;
  change_pct: number | null;
  deviation: number | null;
  days: number | null;
  board: number | null;
  rule_code: number | null;
  rule: string;
  is_today: boolean;
}

export interface MarketPriceAnomaly {
  source: "东方财富";
  date: string;
  fetched_at: string;
  page_no: number;
  page_size: number;
  pages: number;
  is_stale: boolean;
  items: MarketPriceAnomalyItem[];
}

export interface MarketPriceAnomalyCountItem {
  code: string;
  name: string;
  market: MarketPriceAnomalyExchange;
  price: number | null;
  change_pct: number | null;
  times: number | null;
  deviation: number | null;
  days: number | null;
  board: number | null;
}

export interface MarketPriceAnomalyCount {
  source: "东方财富";
  date: string;
  fetched_at: string;
  page_no: number;
  page_size: number;
  pages: number;
  is_stale: boolean;
  items: MarketPriceAnomalyCountItem[];
}

export interface MarketWindStock {
  code: string;
  name: string;
  price: number | null;
  change_pct: number | null;
  limit_up_days: number;
}

export interface MarketWindStocks {
  source: "财联社";
  fetched_at: string;
  plate_code: string;
  items: MarketWindStock[];
}

export interface ThsHotStock {
  rank: number | null;
  code: string;
  name: string;
  change_pct: number | null;
  hot_value: number | null;
  concept_tag: string;
  pop_tag: string;
}

export interface ThsHotPlate {
  rank: number | null;
  code: string;
  name: string;
  change_pct: number | null;
  hot_value: number | null;
  hot_tag: string;
  tag: string;
}

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
}

export interface IndustryRankItem {
  rank: number | null;
  name: string;
  change_pct: number | null;
  code: string;
  up_count: number | null;
  down_count: number | null;
  leader: string;
  leader_change: number | null;
  amount: number | null;
  net_inflow: number | null;
  buy_amount: number | null;
  sell_amount: number | null;
  turnover_rate: number | null;
  market_cap: number | null;
  avg_change: number | null;
}

export interface IndustryRankings {
  sectors: IndustryRankItem[];
  total: number;
  source: string;
  date: string;
  fetched_at: string;
  fund_data_available: boolean;
}

export interface MacroIndicator {
  latest: Record<string, string | number | null> | null;
  trend: Record<string, string | number | null>[];
  source?: string | null;
  source_api?: string | null;
  latest_period?: string | null;
  is_fallback?: boolean;
  is_stale?: boolean;
  field_periods?: Record<string, string>;
  stale_fields?: string[];
}

export interface MacroCategory {
  [indicatorKey: string]: MacroIndicator;
}

export interface MacroUsData {
  indicators: MacroCategory;
  updated_at?: string | null;
  refreshing?: boolean;
  failed_indicators?: Record<string, string>;
}

export interface MacroAllData {
  prices: MacroCategory;
  sentiment: MacroCategory;
  monetary: MacroCategory;
  rates: MacroCategory;
  growth: MacroCategory;
  trade: MacroCategory;
}

export interface MacroFeedItem {
  id: string;
  title: string;
  url: string;
  published_at: string;
  source: string;
}

export interface MacroRateItem {
  key: string;
  label: string;
  value: number | null;
  unit: string;
  period: string;
  change_bp: number | null;
}

export interface MacroFeed {
  period_start: string;
  period_end: string;
  releases: MacroFeedItem[];
  policy_news: MacroFeedItem[];
  policy_readings: MacroFeedItem[];
  rates: MacroRateItem[];
  updated_at: string;
  status: "available" | "partial" | "unavailable";
  failed_sources: string[];
}

export interface MacroAnalysisRef {
  title: string;
  url: string;
}

export interface MacroAnalysisEvent {
  date: string;
  category: string;
  title: string;
  interpretation: string;
  impact: string;
  pending: boolean;
  refs: MacroAnalysisRef[];
}

export interface MacroAnalysis {
  period: string;
  summary: string;
  sentiment: string;
  events: MacroAnalysisEvent[];
  policy_signals: string[];
  degraded: boolean;
  pending_count: number;
  warning: string;
  generated_at: string;
  cached: boolean;
}

export interface TradingCalendar {
  start_date: string;
  end_date: string;
  trade_dates: string[];
  count: number;
  today: string;
  today_is_trading_day: boolean;
  previous_trading_day: string | null;
  next_trading_day: string | null;
  degraded: boolean;
}

export interface TreasuryYieldPoint {
  date: string;
  cn_2y: number | null;
  cn_5y: number | null;
  cn_10y: number | null;
  cn_30y: number | null;
  cn_10y_2y: number | null;
  cn_gdp_growth?: number | null;
  us_2y: number | null;
  us_5y: number | null;
  us_10y: number | null;
  us_30y: number | null;
  us_10y_2y: number | null;
  us_gdp_growth?: number | null;
  spread_10y: number | null;
  spread_2y: number | null;
}

export interface TreasuryTermStructure {
  tenor: string;
  cn_yield: number | null;
  us_yield: number | null;
  spread: number | null;
}

export interface TreasuryYieldsResponse {
  history: TreasuryYieldPoint[];
  term_structure: TreasuryTermStructure[];
  total_count: number;
  latest: {
    date: string;
    china_date?: string;
    us_date?: string;
    china_10y_yield: number | null;
    china_2y_yield: number | null;
    china_5y_yield?: number | null;
    china_30y_yield?: number | null;
    china_10y_2y_spread?: number | null;
    us_10y_yield: number | null;
    us_2y_yield: number | null;
    us_5y_yield?: number | null;
    us_30y_yield?: number | null;
    us_10y_2y_spread: number | null;
    us_china_10y_spread: number | null;
    us_china_spread_status: string;
    us_yield_curve_status: string;
  };
}

export interface GlobalMacroRatesData {
  timestamp: string;
  dollar_and_fx: {
    dxy?: { name: string; code: string; value: number | null; change: number | null; change_pct: number | null };
    usd_cnh?: { name: string; code: string; value: number | null; change: number | null; change_pct: number | null };
    usd_cny?: { name: string; code: string; value: number | null; change: number | null; change_pct: number | null };
  };
  treasury_yields_and_spreads: {
    date: string;
    china_date?: string;
    us_date?: string;
    china_10y_yield: number | null;
    china_2y_yield: number | null;
    china_5y_yield?: number | null;
    china_30y_yield?: number | null;
    china_10y_2y_spread?: number | null;
    us_10y_yield: number | null;
    us_2y_yield: number | null;
    us_5y_yield?: number | null;
    us_30y_yield?: number | null;
    us_china_10y_spread: number | null;
    us_china_spread_status: string;
    us_10y_2y_spread: number | null;
    us_yield_curve_status: string;
  };
  treasury_curve?: {
    history: TreasuryYieldPoint[];
    term_structure: TreasuryTermStructure[];
    total_count: number;
  };
  central_bank_policy_rates: {
    china_lpr_1y: string;
    china_lpr_5y: string;
    us_fed_funds_rate: string;
  };
  market_implications: {
    us_10y_impact: string;
    us_china_spread_impact: string;
    dxy_cnh_impact: string;
  };
  crude_oil?: CrudeOilData | null;
}

export interface CrudeOilQuote {
  symbol: string;
  name: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  unit: string;
  date: string;
}

export interface CrudeOilHistoryPoint {
  date: string;
  sc_close: number | null;
  wti_close: number | null;
  brent_close: number | null;
}

export interface CrudeOilData {
  sc0?: CrudeOilQuote | null;
  wti?: CrudeOilQuote | null;
  brent?: CrudeOilQuote | null;
  history: CrudeOilHistoryPoint[];
}

export interface CommodityItem {
  symbol: string;
  name: string;
  contract: string;
  category: string;
  unit: string;
  latest_price: number | null;
  change: number | null;
  change_pct: number | null;
  high: number | null;
  low: number | null;
  open: number | null;
  prev_settle: number | null;
  volume: number | null;
  open_interest: number | null;
  date: string;
  description: string;
  related_chains: string[];
}

export interface CommoditiesResponse {
  query: string;
  total_count: number;
  items: CommodityItem[];
}

export interface SgeGoldHistoryPoint {
  date: string;
  open: number;
  close: number;
  low: number;
  high: number;
  change: number | null;
  change_pct: number | null;
}

export interface SgeGoldResponse {
  symbol: string;
  name: string;
  unit: string;
  source: string;
  latest: SgeGoldHistoryPoint | null;
  history: SgeGoldHistoryPoint[];
  updated_at: string;
  is_stale: boolean;
  /** 合约已停止交易，最新交易日长期未更新，仅供历史参考。 */
  is_delisted: boolean;
}

export interface CustomsMonthSummary {
  month: string;
  report_date: string;
  export_val: number | null;
  import_val: number | null;
  trade_balance: number | null;
  balance_status: string;
  export_yoy_pct: number | null;
  import_yoy_pct: number | null;
  export_accumulate: number | null;
  import_accumulate: number | null;
  export_accumulate_yoy_pct: number | null;
  import_accumulate_yoy_pct: number | null;
}

export interface CustomsCommodityProfile {
  category: string;
  commodity: string;
  trade_type: string;
  unit: string;
  description: string;
  key_target_markets: string;
  related_a_stocks: string[];
  industry_chains: string[];
}

export interface CustomsTradeDataResponse {
  query: string;
  latest_month_summary: CustomsMonthSummary | null;
  recent_12m_macro_trend: CustomsMonthSummary[];
  matched_commodity_profiles: CustomsCommodityProfile[];
  investment_implications: {
    export_driver: string;
    substitute_driver: string;
  };
}


export type NationalTeamEtfPoint = components["schemas"]["NationalTeamEtfPoint"];
export type NationalTeamEtfSeries = components["schemas"]["NationalTeamEtfSeries"];
export type NationalTeamIndexPoint = components["schemas"]["NationalTeamIndexPoint"];
export type NationalTeamIndexSeries = components["schemas"]["NationalTeamIndexSeries"];
export type NationalTeamSummary = components["schemas"]["NationalTeamSummary"];
export type NationalTeamResponse = components["schemas"]["NationalTeamResponse"];
export type MarketVolumeSeriesItem = components["schemas"]["MarketVolumeSeriesItem"];
export type MarketVolumeResponse = components["schemas"]["MarketVolumeResponse"];
