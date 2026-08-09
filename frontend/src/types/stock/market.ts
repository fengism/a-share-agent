export interface MarketIndices {
  indices: {
    code: string;
    name: string;
    price: number | null;
    change_pct: number | null;
    volume: number | null;
    amount: number | null;
  }[];
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
