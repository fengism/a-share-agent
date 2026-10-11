import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { apiDelete, apiGet, apiPost, apiPut, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  ConceptImportCommitRequest,
  ConceptImportCommitResponse,
  ConceptImportFileRequest,
  ConceptImportPreviewResponse,
  ConceptListResponse,
  ConceptMutationResponse,
  ConceptStatusResponse,
  StockConceptListFilters,
  StockConceptListResponse,
  StockConceptRecordInput,
} from "../stockConcept";

const BASE_PATH = "/stock-concept";

export function useStockConceptStatus() {
  return useQuery({
    queryKey: queryKeys.stockConcept.status,
    queryFn: () => apiGet<ConceptStatusResponse>(`${BASE_PATH}/status`),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useConceptTags(query?: string) {
  return useQuery({
    queryKey: queryKeys.stockConcept.concepts(query),
    queryFn: () => apiGet<ConceptListResponse>(`${BASE_PATH}/concepts`, { query, limit: 1000 }),
    staleTime: QUERY_CACHE_POLICIES.reference.staleMs,
  });
}

export function useStockConceptRecords(filters: StockConceptListFilters) {
  return useQuery({
    queryKey: queryKeys.stockConcept.records(filters),
    queryFn: () => apiGet<StockConceptListResponse>(`${BASE_PATH}/stocks`, {
      query: filters.query,
      market_group: filters.market_group,
      concept: filters.concept,
      page: filters.page,
      page_size: filters.page_size,
    }),
    placeholderData: (previous) => previous,
  });
}

function useInvalidateStockConceptData() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.stockConcept.root });
}

export function useCreateStockConceptRecord() {
  const invalidate = useInvalidateStockConceptData();
  return useMutation({
    mutationFn: (record: StockConceptRecordInput) =>
      apiPost<ConceptMutationResponse>(`${BASE_PATH}/records`, record),
    onSuccess: invalidate,
  });
}

export function useUpdateStockConceptRecord() {
  const invalidate = useInvalidateStockConceptData();
  return useMutation({
    mutationFn: ({ id, record }: { id: number; record: StockConceptRecordInput & { expected_revision: string } }) =>
      apiPut<ConceptMutationResponse>(`${BASE_PATH}/records/${id}`, record),
    onSuccess: invalidate,
  });
}

export function useDeleteStockConceptRecord() {
  const invalidate = useInvalidateStockConceptData();
  return useMutation({
    mutationFn: (id: number) => apiDelete<ConceptMutationResponse>(`${BASE_PATH}/records/${id}`),
    onSuccess: invalidate,
  });
}

export function usePreviewStockConceptImport() {
  return useMutation({
    mutationFn: (request: ConceptImportFileRequest) =>
      apiPost<ConceptImportPreviewResponse>(`${BASE_PATH}/import/preview`, request, {
        timeoutMs: API_TIMEOUTS.LONG_RUNNING,
      }),
  });
}

export function useCommitStockConceptImport() {
  const invalidate = useInvalidateStockConceptData();
  return useMutation({
    mutationFn: (request: ConceptImportCommitRequest) =>
      apiPost<ConceptImportCommitResponse>(`${BASE_PATH}/import/commit`, request, {
        timeoutMs: API_TIMEOUTS.LONG_RUNNING,
      }),
    onSuccess: invalidate,
  });
}

export function useTriggerStockConceptEnrich() {
  const invalidate = useInvalidateStockConceptData();
  return useMutation({
    mutationFn: (params?: { batch_size?: number; delay_seconds?: number }) => {
      const qs = new URLSearchParams();
      if (params?.batch_size) qs.set("batch_size", String(params.batch_size));
      if (params?.delay_seconds) qs.set("delay_seconds", String(params.delay_seconds));
      const url = qs.toString() ? `${BASE_PATH}/enrich?${qs.toString()}` : `${BASE_PATH}/enrich`;
      return apiPost<{ success: boolean; data: { processed: number; enriched: number; remaining: number } }>(
        url,
        null,
        { timeoutMs: API_TIMEOUTS.LONG_RUNNING }
      );
    },
    onSuccess: invalidate,
  });
}

