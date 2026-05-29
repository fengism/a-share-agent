export interface DailyReviewSection {
  title: string;
  summary: string;
  bullets: string[];
}

export interface DailyReviewDataSnapshot {
  indices: Record<string, unknown>[];
  hot_stocks: Record<string, unknown>[];
  hot_concepts: Record<string, unknown>[];
  hot_industries: Record<string, unknown>[];
  dragon_tiger: Record<string, unknown>[];
  top_sectors: Record<string, unknown>[];
  bottom_sectors: Record<string, unknown>[];
}

export interface DailyReviewResult {
  date: string;
  title: string;
  generated_at: string;
  market_summary: string;
  llm_review: string;
  index_review: DailyReviewSection;
  hotspot_review: DailyReviewSection;
  dragon_tiger_review: DailyReviewSection;
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
}

export interface DailyReviewRequest {
  date?: string | null;
  force?: boolean;
}
