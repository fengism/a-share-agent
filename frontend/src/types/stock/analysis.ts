import type { StockBasicInfo } from "./profile";
import type { IntradayData, KlineData } from "./quotes";
import type { StockValuation } from "./valuation";

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
  can_delete: boolean;
}

export interface AnalysisPageData {
  stock_info: StockBasicInfo | null;
  kline: KlineData | null;
  intraday: IntradayData | null;
  valuation: StockValuation | null;
  cached_analysis: AnalysisResult | null;
}
