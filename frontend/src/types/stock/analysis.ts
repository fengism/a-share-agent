import type { ChatStreamDelta } from "../chat";
import type { StockBasicInfo } from "./profile";
import type { ChipDistribution, IntradayData, KlineData } from "./quotes";
import type { StockValuation } from "./valuation";

export interface FactorAnalysis {
  score: number;
  summary: string;
  strengths: string[];
  risks: string[];
  trend?: string | null;
  support_level?: number | null;
  resistance_level?: number | null;
  key_signals?: string[];
  market_mood?: string | null;
  heat_level?: string | null;
}

export type InformationGrade = "A" | "B" | "C" | "unknown";
export type AssessmentLevel = "strong" | "moderate" | "weak" | "unclear";
export type AssessmentDirection = "strengthening" | "stable" | "weakening" | "unclear";
export type RiskLevel = "high" | "medium" | "low" | "unknown";
export type ScenarioName = "bull" | "base" | "bear";

export interface InformationQuality {
  grade: InformationGrade;
  grade_rationale: string;
  evidence_confidence: number | null;
  investment_certainty: number | null;
  coverage_summary: string;
  limitations: string[];
}

export interface SegmentQuality {
  segment: string;
  role: string;
  growth_quality: string;
  profitability_quality: string;
  recurrence: string;
  evidence_confidence: number | null;
}

export interface BusinessModelResearch {
  economic_engine: string;
  revenue_drivers: string[];
  segment_quality: SegmentQuality[];
  earnings_quality: string;
  operating_leverage: string;
  strengths: string[];
  concerns: string[];
}

export interface MoatItem {
  moat_type: "brand_pricing" | "switching_cost" | "network_effect" | "scale_advantage" | "technology_ip" | "other";
  evidence: string[];
  counterevidence: string[];
  strength: AssessmentLevel;
  direction: AssessmentDirection;
  durability: string;
  threats: string[];
  confidence: number | null;
}

export interface MoatAssessment {
  moats: MoatItem[];
  overall_durability: string;
  key_threats: string[];
}

export interface ManagementAssessment {
  track_record: string;
  capital_allocation: string;
  shareholder_alignment: string;
  succession_or_key_person_risk: string;
  strengths: string[];
  concerns: string[];
  confidence: number | null;
}

export interface IndustryPosition {
  secular_context: string;
  value_chain_position: string;
  growth_drivers: string[];
  competitive_position: string;
  technology_or_obsolescence_risk: string;
  concentration_risks: string[];
  confidence: number | null;
}

export interface RiskCase {
  risk: string;
  failure_path: string;
  probability: RiskLevel;
  impact: RiskLevel;
  time_horizon: string;
  leading_indicators: string[];
  mitigants: string[];
  scenario: ScenarioName | "cross_scenario";
}

export interface InversionAnalysis {
  bear_case: string;
  risks: RiskCase[];
  bias_checks: string[];
}

export interface ValuationScenario {
  scenario: ScenarioName;
  assumptions: string[];
  valuation_view: string;
  fair_value_range: [number, number] | null;
  key_drivers: string[];
  invalidating_conditions: string[];
}

export interface ValuationScenarios {
  bull: ValuationScenario;
  base: ValuationScenario;
  bear: ValuationScenario;
}

export interface ValuationFramework {
  method_summary: string;
  current_valuation: string;
  assumptions: string[];
  scenarios: ValuationScenarios | null;
  margin_of_safety: string;
  limitations: string[];
}

export interface InvestorActionPlan {
  new_investor_action: "buy" | "watch" | "avoid" | "insufficient_evidence";
  holder_action: "hold" | "add" | "reduce" | "exit" | "insufficient_evidence";
  rationale: string;
  buy_or_add_range: [number, number] | null;
  add_triggers: string[];
  sell_triggers: string[];
  thesis_breakers: string[];
  monitoring_metrics: string[];
}

export interface DataGap {
  topic: string;
  missing_data: string;
  decision_impact: string;
  follow_up: string;
}

export interface InvestmentResearchFramework {
  information_quality: InformationQuality;
  business_model: BusinessModelResearch;
  moat: MoatAssessment;
  management: ManagementAssessment;
  industry_position: IndustryPosition;
  inversion: InversionAnalysis;
  valuation: ValuationFramework;
  actions: InvestorActionPlan;
  data_gaps: DataGap[];
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
  research_framework?: InvestmentResearchFramework | null;
  prompt_trace?: {
    prompt_id?: string;
    prompt_version?: string;
    model?: string;
    generated_at?: string;
    attempts?: number;
  } | null;
  agent_trace?: ChatStreamDelta[];
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

export interface AnalysisKeyLevels {
  current_price: number | null;
  support: number | null;
  resistance: number | null;
}

export interface AnalysisPageData {
  stock_info: StockBasicInfo | null;
  kline: KlineData | null;
  intraday: IntradayData | null;
  valuation: StockValuation | null;
  cached_analysis: AnalysisResult | null;
  key_levels: AnalysisKeyLevels | null;
  chip_distribution: ChipDistribution | null;
  partial?: boolean;
  unavailable_sections?: Array<"stock_info" | "kline" | "intraday" | "valuation" | "cached_analysis">;
}
