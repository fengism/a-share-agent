export interface IndustryChainChart {
  title: string;
  description?: string;
  type: string;
  option: Record<string, unknown>;
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
  [key: string]: unknown;
}

export interface IndustryChainMetric {
  label: string;
  value: string;
  period?: string;
  growth?: string;
  source?: string;
  source_url?: string;
}

export interface IndustryChainInsight {
  title: string;
  detail?: string;
  evidence?: string;
  source?: string;
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
}

export interface IndustryChainSource {
  title: string;
  publisher?: string;
  date?: string;
  url?: string;
}

export interface IndustryChainResult {
  schema_version?: number;
  name: string;
  aliases?: string[];
  summary: string;
  positioning?: string;
  market_metrics?: IndustryChainMetric[];
  competition?: IndustryChainCompetitionGroup[];
  technology_routes?: IndustryChainInsight[];
  upstream: IndustryChainNode[];
  midstream: IndustryChainNode[];
  downstream: IndustryChainNode[];
  drivers: string[];
  trends?: IndustryChainInsight[];
  risks: string[];
  capital_moves?: IndustryChainInsight[];
  key_events?: IndustryChainEvent[];
  key_stocks: IndustryChainNode[];
  sources?: IndustryChainSource[];
  llm_review: string;
  charts: IndustryChainChart[];
}

export interface IndustryChainHistoryItem {
  name: string;
  archive_id: string;
  saved_at: string;
  title: string;
  summary: string;
  can_delete: boolean;
}
