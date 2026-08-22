export interface IndustryChainChart {
  title: string;
  description?: string;
  type: string;
  option: Record<string, unknown>;
}

export interface IndustryChainResearchScope {
  region: "china" | "global" | "china_and_global";
  time_range: "half_year" | "one_year" | "three_years" | "custom";
  start_date?: string;
  end_date?: string;
  as_of_date?: string;
  company_scope: "a_share" | "all_public";
}

export interface IndustryChainNode {
  name?: string | null;
  company?: string | null;
  code?: string | null;
  role?: string;
  description?: string;
  companies?: string[];
  market_share?: string;
  metric?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
  [key: string]: unknown;
}

export interface IndustryChainMetric {
  label: string;
  value: string;
  period?: string;
  growth?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
}

export interface IndustryChainInsight {
  title: string;
  detail?: string;
  evidence?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
}

export interface IndustryChainCompetitionGroup {
  market: string;
  summary?: string;
  companies: IndustryChainNode[];
}

export interface IndustryChainEvent {
  date?: string;
  title: string;
  impact?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
}

export interface IndustryChainSource {
  title: string;
  publisher?: string;
  date?: string;
  url?: string;
  evidence_ids?: string[];
}

export interface IndustryChainEvidence {
  evidence_id: string;
  tool_name: string;
  provider?: string;
  arguments?: string;
  title?: string;
  source_urls?: string[];
  published_at?: string;
  fetched_at?: string;
  truncated?: boolean;
  content_preview?: string;
  status?: "success" | "error";
  error_message?: string;
}

export interface IndustryChainEvidenceStats {
  total_count?: number;
  unique_count?: number;
  selected_count?: number;
  omitted_count?: number;
  failed_count?: number;
  prompt_characters?: number;
}

export interface IndustryChainCoverage {
  market?: "complete" | "partial" | "missing";
  competition?: "complete" | "partial" | "missing";
  technology?: "complete" | "partial" | "missing";
  chain?: "complete" | "partial" | "missing";
  companies?: "complete" | "partial" | "missing";
  events?: "complete" | "partial" | "missing";
}

export interface IndustryChainConflict {
  topic: string;
  values?: string[];
  reason?: string;
  evidence_ids?: string[];
}

export interface IndustryChainResult {
  schema_version?: number;
  name: string;
  aliases?: string[];
  summary: string;
  positioning?: string;
  summary_evidence_ids?: string[];
  positioning_evidence_ids?: string[];
  market_metrics?: IndustryChainMetric[];
  competition?: IndustryChainCompetitionGroup[];
  technology_routes?: IndustryChainInsight[];
  upstream: IndustryChainNode[];
  midstream: IndustryChainNode[];
  downstream: IndustryChainNode[];
  drivers: string[];
  driver_insights?: IndustryChainInsight[];
  trends?: IndustryChainInsight[];
  risks: string[];
  risk_insights?: IndustryChainInsight[];
  capital_moves?: IndustryChainInsight[];
  key_events?: IndustryChainEvent[];
  key_stocks: IndustryChainNode[];
  sources?: IndustryChainSource[];
  llm_review: string;
  charts: IndustryChainChart[];
  quality_status?: "complete" | "degraded";
  archive_status?: "none" | "saved" | "failed";
  archive_id?: string;
  warnings?: string[];
  research_scope?: Record<string, string>;
  evidence_catalog?: IndustryChainEvidence[];
  evidence_stats?: IndustryChainEvidenceStats;
  coverage?: IndustryChainCoverage;
  missing_evidence?: string[];
  conflicts?: IndustryChainConflict[];
}

export interface IndustryChainHistoryItem {
  name: string;
  archive_id: string;
  saved_at: string;
  title: string;
  summary: string;
  can_delete: boolean;
}
