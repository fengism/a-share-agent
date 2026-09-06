export type StockConceptMarketGroup = "A" | "HK" | "OVERSEAS";

export interface StockConceptRecordInput {
  market_group: StockConceptMarketGroup;
  exchange_suffix: string;
  stock_code: string;
  stock_name?: string;
  concepts: string[];
  source_version?: string;
}

export interface StockConceptRecord extends StockConceptRecordInput {
  id: number;
  source: string;
  is_manual_override: boolean;
  created_at: string;
  updated_at: string;
}

export interface StockConceptListResponse {
  items: StockConceptRecord[];
  total: number;
  page: number;
  page_size: number;
}

export interface ConceptItem {
  name: string;
  stock_count: number;
}

export interface ConceptListResponse {
  items: ConceptItem[];
  total: number;
}

export interface ConceptStats {
  total_stocks: number;
  total_concepts: number;
  market_counts: Record<string, number>;
  latest_updated_at?: string | null;
}

export interface ConceptStatusResponse {
  stats: ConceptStats;
}

export interface ConceptImportFileRequest {
  filename: string;
  content_base64: string;
  source_version?: string;
}

export interface ConceptImportPreviewResponse {
  import_token: string;
  content_hash: string;
  total_rows: number;
  valid_rows: number;
  added_rows: number;
  updated_rows: number;
  unchanged_rows: number;
  skipped_rows: number;
  invalid_rows: number;
  warnings: string[];
  sample: Array<Record<string, unknown>>;
}

export interface ConceptImportCommitRequest extends ConceptImportFileRequest {
  import_token: string;
  force_override?: boolean;
}

export interface ConceptImportCommitResponse {
  added: number;
  updated: number;
  unchanged: number;
  skipped: number;
}

export interface ConceptMutationResponse {
  success: boolean;
  id?: number | null;
}

export interface StockConceptListFilters {
  query?: string;
  market_group?: "" | StockConceptMarketGroup;
  concept?: string;
  page: number;
  page_size: number;
}
