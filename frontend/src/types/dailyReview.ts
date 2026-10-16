export interface DailyReviewSection {
  title: string;
  summary: string;
  bullets: string[];
}

export interface DailyReviewDataSnapshot {
  requested_date?: string;
  effective_date?: string;
  source_status?: Record<string, {
    status: "complete" | "partial" | "unavailable";
    requested_date?: string;
    data_date?: string;
    provider?: string;
    is_realtime?: boolean;
    error?: string;
  }>;
  indices: Record<string, unknown>[];
  hot_stocks: Record<string, unknown>[];
  hot_concepts: Record<string, unknown>[];
  hot_industries: Record<string, unknown>[];
  dragon_tiger: Record<string, unknown>[];
  market_statistics: Record<string, unknown>;
  market_news: Record<string, unknown>[];
  policy_news?: Array<{
    title: string;
    content?: string;
    source?: string;
    publish_time?: string;
    url?: string;
    event_type?: "policy" | "macro" | "global" | "industry" | "market";
    direction?: "positive" | "negative" | "mixed" | "neutral";
    timing?: "before" | "on_date" | "after";
    related_sectors?: string[];
    corroborating_sources?: string[];
  }>;
  top_sectors: Record<string, unknown>[];
  bottom_sectors: Record<string, unknown>[];
  market_volume: Record<string, unknown>;
  macro_data: Record<string, unknown>;
  macro_analysis?: Record<string, unknown>;
}

export interface DailyReviewEventImpact {
  event_title: string;
  event_type: "policy" | "macro" | "global" | "industry" | "market";
  direction: "positive" | "negative" | "mixed" | "neutral";
  timing: "before" | "on_date" | "after";
  horizon: "intraday" | "short_term" | "medium_term";
  affected_sectors: string[];
  transmission_chain: string;
  evidence: string;
  market_confirmation?: string;
  confirmation_signals: string[];
  invalidation_conditions: string[];
}

export interface DailyReviewSentimentCycle {
  stage: "冰点" | "修复回暖" | "主升共振" | "高位分化" | "退潮杀跌";
  ladder_health?: string;
  evidence: string[];
}

export interface DailyReviewScenario {
  name: "超预期" | "符合预期" | "低于预期";
  trigger?: string;
  playbook?: string;
  watch_levels: string[];
}

export interface DailyReviewWatchItem {
  name: string;
  code?: string;
  role: "总龙头" | "连板最高板" | "中军容量票" | "负反馈票";
  reason?: string;
  trigger?: string;
}

export interface DailyReviewWatchCheck {
  name: string;
  code?: string;
  role?: string;
  change_pct?: number | null;
  hit: boolean;
  limit_up: boolean;
  missing: boolean;
}

export interface DailyReviewIndexCheck {
  code?: string;
  name: string;
  previous_change_pct?: number | null;
  change_pct?: number | null;
}

export interface DailyReviewPreviousCheck {
  review_date: string;
  verified_date: string;
  indices?: DailyReviewIndexCheck[];
  watchlist?: DailyReviewWatchCheck[];
  hit_count: number;
  checked_count: number;
  hit_rate?: number | null;
  previous_stage?: string;
  limit_up_count?: number | null;
  previous_limit_up_count?: number | null;
  limit_up_delta?: number | null;
  note?: string;
}

export interface CycleTrendPoint {
  date: string;
  stage?: string;
  ladder_health?: string;
  limit_up_count?: number | null;
  limit_down_count?: number | null;
  break_rate?: number | null;
  up_down_ratio?: number | null;
  index_change_pct?: number | null;
  next_index_change_pct?: number | null;
  stage_transition?: string;
}

export interface CycleStageStat {
  stage: string;
  occurrences: number;
  next_day_up_ratio?: number | null;
  avg_next_day_index_change_pct?: number | null;
  avg_limit_up_delta?: number | null;
}

export interface CycleTrend {
  points?: CycleTrendPoint[];
  stage_stats?: CycleStageStat[];
  note?: string;
}

export interface DailyReviewResult {
  schema_version?: number;
  date: string;
  requested_date?: string;
  effective_date?: string;
  session_status?: "completed" | "adjusted";
  quality_status?: "complete" | "degraded";
  generation_status?: "llm" | "fallback";
  warnings?: string[];
  notes?: string[];
  source_errors?: Record<string, string>;
  llm_error?: string;
  market_state?: "attack" | "balanced" | "defensive" | "unknown";
  position_range?: string;
  invalid_conditions?: string[];
  data_gaps?: string[];
  prompt_trace?: Record<string, unknown> | null;
  title: string;
  generated_at: string;
  market_summary: string;
  llm_review: string;
  index_review: DailyReviewSection;
  hotspot_review: DailyReviewSection;
  dragon_tiger_review: DailyReviewSection;
  news_policy_review?: DailyReviewSection;
  event_impacts?: DailyReviewEventImpact[];
  sentiment_cycle?: DailyReviewSentimentCycle | null;
  scenario_plans?: DailyReviewScenario[];
  next_day_watchlist?: DailyReviewWatchItem[];
  key_levels?: string[];
  previous_review_check?: DailyReviewPreviousCheck | null;
  cycle_trend?: CycleTrend | null;
  risk_alerts: string[];
  opportunities: string[];
  strategy_notes: string[];
  data_snapshot: DailyReviewDataSnapshot;
}

export interface DailyReviewHistoryItem {
  date: string;
  title: string;
  generated_at: string;
  market_summary: string;
  can_delete: boolean;
}

export interface DailyReviewRequest {
  date?: string | null;
  force?: boolean;
}
