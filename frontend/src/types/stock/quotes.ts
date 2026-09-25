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
  source?: string | null;
  adjustment_verified?: boolean;
  items: KlineItem[];
}

export interface ChipCostRange {
  low: number;
  high: number;
}

export interface ChipHistogramItem {
  price: number;
  ratio: number;
}

export interface ChipDistribution {
  code: string;
  as_of_date: string;
  source: string;
  price: number;
  profit_ratio: number;
  avg_cost: number;
  cost_90: ChipCostRange;
  cost_70: ChipCostRange;
  concentration_90: number | null;
  concentration_70: number | null;
  peak_price: number;
  histogram: ChipHistogramItem[];
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
  source: string;
  prev_close: number | null;
  items: IntradayItem[];
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

export interface StockFundFlowItem {
  date: string;
  main_net: number | null;
  small_net: number | null;
  mid_net: number | null;
  large_net: number | null;
  super_net: number | null;
  source: string;
  source_api: string;
  is_stale?: boolean;
}

export interface StockFundFlowPage {
  items: StockFundFlowItem[];
  total: number;
  next_cursor: string | null;
  source: string;
  source_api: string;
}
