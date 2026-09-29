import type { components } from "./generated/schema";

export type StockBasicProfileRecord = components["schemas"]["StockBasicProfileRecord"];
export type StockBasicProfileInput = components["schemas"]["StockBasicProfileInput"];
export type StockBasicProfileListResponse = components["schemas"]["StockBasicProfileListResponse"];
export type StockBasicProfileSummary = components["schemas"]["StockBasicProfileSummary"];
export type StockProfileEnrichResponse = components["schemas"]["StockProfileEnrichResponse"];
export type StockProfileImportFileRequest = components["schemas"]["StockProfileImportFileRequest"];
export type StockProfileImportResponse = components["schemas"]["StockProfileImportResponse"];

export interface StockProfileListFilters {
  q?: string;
  market_group?: string;
  exchange?: string;
  board?: string;
  has_business?: boolean;
  has_listing_date?: boolean;
  page: number;
  page_size: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export type StockProfileSyncResponse = components["schemas"]["StockProfileSyncResponse"];
