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
  updated_at: string;
  unit: string;
  points: HsgtFlowPoint[];
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
  source: "财联社";
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
  source: "开盘红";
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
  source: "开盘红";
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
  amount: number;
  turnover_rate: number | null;
  float_amount: number;
  main_buy: number;
  main_sell: number;
  main_net: number;
  buy_ratio: number | null;
  sell_ratio: number | null;
  net_ratio: number | null;
  limit_tag: string;
  rank_tag: string;
  recent_chg: number | null;
  limit_count: number;
  chg_1d: number | null;
  chg_5d: number | null;
  chg_20d: number | null;
}

export interface MarketSectorStocksHistory {
  source: "开盘红";
  date: string;
  plate_id: string;
  fetched_at: string;
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
