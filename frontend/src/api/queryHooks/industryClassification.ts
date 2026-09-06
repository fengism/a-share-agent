import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, apiPut, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  IndustryHierarchyResponse,
  IndustryImportCommitRequest,
  IndustryImportCommitResponse,
  IndustryImportFileRequest,
  IndustryImportPreviewResponse,
  IndustryListFilters,
  IndustryListResponse,
  IndustryMutationResponse,
  IndustryRecordInput,
  IndustryRefreshPolicyRequest,
  IndustryRefreshResponse,
  IndustryStatusResponse,
} from "../industryClassification";

const BASE_PATH = "/industry-classification";

export function useIndustryStatus() {
  return useQuery({
    queryKey: queryKeys.industryClassification.status,
    queryFn: () => apiGet<IndustryStatusResponse>(`${BASE_PATH}/status`),
  });
}

export function useIndustryHierarchy(filters: Pick<IndustryListFilters, "market_group" | "level1" | "level2">) {
  return useQuery({
    queryKey: queryKeys.industryClassification.hierarchy(
      filters.market_group ?? "",
      filters.level1 ?? "",
      filters.level2 ?? "",
    ),
    queryFn: () => apiGet<IndustryHierarchyResponse>(`${BASE_PATH}/industries`, filters),
  });
}

export function useIndustryRecords(filters: IndustryListFilters) {
  return useQuery({
    queryKey: queryKeys.industryClassification.records(filters),
    queryFn: () => apiGet<IndustryListResponse>(`${BASE_PATH}/stocks`, {
      query: filters.query,
      market_group: filters.market_group,
      level1: filters.level1,
      level2: filters.level2,
      level3: filters.level3,
      page: filters.page,
      page_size: filters.page_size,
    }),
    placeholderData: (previous) => previous,
  });
}

function useInvalidateIndustryData() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.industryClassification.root });
}

export function useCreateIndustryRecord() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: (record: IndustryRecordInput) =>
      apiPost<IndustryMutationResponse>(`${BASE_PATH}/records`, record),
    onSuccess: invalidate,
  });
}

export function useUpdateIndustryRecord() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: ({ id, record }: { id: number; record: IndustryRecordInput }) =>
      apiPut<IndustryMutationResponse>(`${BASE_PATH}/records/${id}`, record),
    onSuccess: invalidate,
  });
}

export function useDeleteIndustryRecord() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: (id: number) => apiDelete<IndustryMutationResponse>(`${BASE_PATH}/records/${id}`),
    onSuccess: invalidate,
  });
}

export function usePreviewIndustryImport() {
  return useMutation({
    mutationFn: (request: IndustryImportFileRequest) =>
      apiPost<IndustryImportPreviewResponse>(`${BASE_PATH}/import/preview`, request, {
        timeoutMs: API_TIMEOUTS.LONG_RUNNING,
      }),
  });
}

export function useCommitIndustryImport() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: (request: IndustryImportCommitRequest) =>
      apiPost<IndustryImportCommitResponse>(`${BASE_PATH}/import/commit`, request, {
        timeoutMs: API_TIMEOUTS.LONG_RUNNING,
      }),
    onSuccess: invalidate,
  });
}

export function useRefreshIndustries() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: () => apiPost<IndustryRefreshResponse>(`${BASE_PATH}/refresh`, undefined, {
      timeoutMs: API_TIMEOUTS.LONG_RUNNING,
    }),
    onSuccess: invalidate,
  });
}

export function useUpdateIndustryRefreshPolicy() {
  const invalidate = useInvalidateIndustryData();
  return useMutation({
    mutationFn: (request: IndustryRefreshPolicyRequest) =>
      apiPut<IndustryStatusResponse>(`${BASE_PATH}/refresh-policy`, request),
    onSuccess: invalidate,
  });
}
