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

export interface DailyReviewResult {
  schema_version?: number;
  date: string;
  requested_date?: string;
  effective_date?: string;
  session_status?: "completed" | "adjusted";
  quality_status?: "complete" | "degraded";
  generation_status?: "llm" | "fallback";
  warnings?: string[];
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
