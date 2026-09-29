import type { ChatStreamDelta } from "../chat";

export interface IndustryChainChart {
  title: string;
  description?: string;
  type: string;
  option: Record<string, unknown>;
}

export type IndustryRefreshDimension = "market" | "stocks" | "competition" | "technology" | "chain" | "drivers_risks" | "reports" | "events";

export interface IndustryChainResearchScope {
  region: "china" | "global" | "china_and_global";
  time_range: "half_year" | "one_year" | "three_years" | "custom";
  start_date?: string;
  end_date?: string;
  as_of_date?: string;
  company_scope: "a_share" | "all_public";
  refresh_dimensions?: IndustryRefreshDimension[];
}

export interface IndustryChainClaim {
  evidence_basis?: "disclosed" | "forecast" | "inference" | "opinion";
  claim_type?: "fact" | "inference" | "opinion";
  citations?: Array<{ evidence_id: string; quote: string; source_url?: string; location?: string }>;
  verification_status?: "unverified" | "quote_matched";
  verification_notes?: string[];
}

export interface IndustryChainNode extends IndustryChainClaim {
  name?: string | null;
  company?: string | null;
  code?: string | null;
  role?: string;
  description?: string;
  companies?: string[];
  business_relevance?: "unverified" | "concept" | "business" | "earnings";
  revenue_share?: string;
  revenue_period?: string;
  benefit_path?: string;
  realization_conditions?: string[];
  invalidation_conditions?: string[];
  tracking_metrics?: string[];
  market_share?: string;
  metric?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
  [key: string]: unknown;
}

export interface IndustryChainMetric extends IndustryChainClaim {
  label: string;
  value: string;
  period?: string;
  growth?: string;
  metric_id?: string;
  numeric_value?: string;
  unit?: string;
  region?: string;
  statistical_scope?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
}

export interface IndustryChainInsight extends IndustryChainClaim {
  title: string;
  detail?: string;
  evidence?: string;
  source?: string;
  source_url?: string;
  evidence_ids?: string[];
  claim_type?: "fact" | "inference" | "opinion";
  confidence?: "high" | "medium" | "low";
}

export interface IndustryChainThesis extends IndustryChainInsight {
  chain_path?: string[];
  mechanism?: string;
  conditions?: string[];
  counter_evidence?: string;
  invalidation?: string;
  tracking_metrics?: string[];
  beneficiaries?: string[];
}

export interface IndustryChainRelationship extends IndustryChainInsight {
  driver?: string;
  target_metric?: string;
  time_lag?: string;
  tracking_metrics?: string[];
  source_node: string;
  target_node: string;
  relation_type: "supply" | "purchase" | "substitute" | "compete" | "transmission";
  impact_direction?: "positive" | "negative" | "mixed" | "unknown";
  conditions?: string[];
  invalidation?: string;
}

export interface IndustryChainCompetitionGroup {
  market: string;
  summary?: string;
  companies: IndustryChainNode[];
}

export interface IndustryChainEvent extends IndustryChainClaim {
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
  material_type?: "discovery" | "body" | "structured" | "unknown";
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

export interface IndustryChainChangeItem {
  category: "chain" | "company" | "market" | "event" | "driver" | "risk" | "summary";
  change_type: "added" | "removed" | "updated";
  title: string;
  detail?: string;
  before?: string;
  after?: string;
  change_basis?: "fact" | "observation" | "evidence" | "text";
  numeric_delta?: string;
  percentage_delta?: string;
}

export interface IndustryChainChangeSet {
  previous_archive_id: string;
  comparable?: boolean;
  comparison_note?: string;
  has_changes: boolean;
  added_count: number;
  removed_count: number;
  updated_count: number;
  items: IndustryChainChangeItem[];
}

export interface IndustryChainOpportunity {
  name: string;
  code?: string;
  role?: string;
  prosperity_score: number;
  earnings_score: number;
  valuation_score: number;
  catalyst_score: number;
  evidence_score: number;
  risk_score: number;
  total_score: number;
  scoring_version?: number;
  score_kind?: "research_completeness";
  completeness_score?: number;
  fundamental_status?: "not_evaluated";
  rationale?: string;
  evidence_ids?: string[];
}

export interface IndustryChainTopicResolution {
  requested_name?: string;
  normalized_name?: string;
  aliases?: string[];
  matched_sectors?: string[];
  possible_topics?: string[];
  boundary_note?: string;
}

export interface IndustryChainAnalysisMetadata {
  total_duration_ms?: number;
  research_duration_ms?: number;
  synthesis_duration_ms?: number;
  draft_duration_ms?: number;
  verification_duration_ms?: number;
  finalization_duration_ms?: number;
  archive_duration_ms?: number;
  cache_hits?: string[];
  cache_misses?: string[];
  failed_dimensions?: string[];
  successful_dimensions?: string[];
  agent_evidence_count?: number;
  public_item_count?: number;
  independent_source_count?: number;
}

export interface IndustryChainResult {
  research_theses?: IndustryChainThesis[];
  verification_repair?: {
    status?: "not_needed" | "completed" | "no_new_evidence" | "failed";
    attempted_rounds?: number;
    added_evidence_count?: number;
    targets?: string[];
    note?: string;
  };
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
  agent_trace?: ChatStreamDelta[];
  changes?: IndustryChainChangeSet;
  opportunities?: IndustryChainOpportunity[];
  relationships?: IndustryChainRelationship[];
  topic_resolution?: IndustryChainTopicResolution;
  analysis_metadata?: IndustryChainAnalysisMetadata;
}

export interface IndustryChainHistoryItem {
  name: string;
  archive_id: string;
  saved_at: string;
  title: string;
  summary: string;
  can_delete: boolean;
}

// ── 产业链知识库（Atlas）──

export interface AtlasCompany {
  name: string;
  code: string;
  note?: string;
}

export interface AtlasSegment {
  name: string;
  description?: string;
  companies: AtlasCompany[];
}

export interface AtlasLayer {
  key: "upstream" | "midstream" | "downstream";
  name: string;
  segments: AtlasSegment[];
}

export interface AtlasChain {
  slug: string;
  name: string;
  category: string;
  summary: string;
  source?: "builtin" | "imported" | "mined";
  aliases?: string[];
  tags?: string[];
  drivers?: string[];
  layers: AtlasLayer[];
}

export interface AtlasChainSummary {
  slug: string;
  name: string;
  category: string;
  summary: string;
  source?: "builtin" | "imported" | "mined";
  aliases?: string[];
  tags?: string[];
  segment_count: number;
  company_count: number;
}

export interface AtlasCatalog {
  categories: string[];
  chains: AtlasChainSummary[];
  total_chains: number;
  total_companies: number;
}
