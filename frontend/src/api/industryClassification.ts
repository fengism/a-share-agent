import type { components } from "./generated/schema";

export type IndustryRecord = components["schemas"]["IndustryRecord"];
export type IndustryRecordInput = components["schemas"]["IndustryRecordInput"];
export type IndustryListResponse = components["schemas"]["IndustryListResponse"];
export type IndustryHierarchyResponse = components["schemas"]["IndustryHierarchyResponse"];
export type IndustryStatusResponse = components["schemas"]["IndustryStatusResponse"];
export type IndustryImportFileRequest = components["schemas"]["ImportFileRequest"];
export type IndustryImportCommitRequest = components["schemas"]["ImportCommitRequest"];
export type IndustryImportPreviewResponse = components["schemas"]["ImportPreviewResponse"];
export type IndustryImportCommitResponse = components["schemas"]["ImportCommitResponse"];
export type IndustryRefreshPolicyRequest = components["schemas"]["RefreshPolicyRequest"];
export type IndustryRefreshResponse = components["schemas"]["RefreshResponse"];
export type IndustryMutationResponse = components["schemas"]["MutationResponse"];

export type IndustryMarketGroup = IndustryRecordInput["market_group"];

export interface IndustryListFilters {
  query?: string;
  market_group?: "" | IndustryMarketGroup;
  level1?: string;
  level2?: string;
  level3?: string;
  page: number;
  page_size: number;
}
