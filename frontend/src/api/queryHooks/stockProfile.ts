import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, apiPut, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  StockBasicProfileInput,
  StockBasicProfileListResponse,
  StockBasicProfileRecord,
  StockBasicProfileSummary,
  StockProfileEnrichResponse,
  StockProfileImportFileRequest,
  StockProfileImportResponse,
  StockProfileListFilters,
} from "../stockProfile";

const BASE_PATH = "/stock-profile";

export function useStockProfileSummary() {
  return useQuery({
    queryKey: queryKeys.stockProfile.summary,
    queryFn: () => apiGet<StockBasicProfileSummary>(`${BASE_PATH}/summary`),
  });
}

export function useStockProfileRecords(filters: StockProfileListFilters) {
  return useQuery({
    queryKey: queryKeys.stockProfile.records(filters),
    queryFn: () =>
      apiGet<StockBasicProfileListResponse>(`${BASE_PATH}/records`, {
        q: filters.q,
        market_group: filters.market_group,
        exchange: filters.exchange,
        board: filters.board,
        has_business: filters.has_business,
        has_listing_date: filters.has_listing_date,
        page: filters.page,
        page_size: filters.page_size,
        sort_by: filters.sort_by,
        sort_order: filters.sort_order,
      }),
    placeholderData: (previous) => previous,
  });
}

export function useStockProfileRecord(code: string) {
  return useQuery({
    queryKey: queryKeys.stockProfile.record(code),
    queryFn: () => apiGet<StockBasicProfileRecord>(`${BASE_PATH}/records/${encodeURIComponent(code)}`),
    enabled: Boolean(code),
  });
}

function useInvalidateStockProfileData() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: queryKeys.stockProfile.root });
}

export function useCreateStockProfileRecord() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: (record: StockBasicProfileInput) =>
      apiPost<StockBasicProfileRecord>(`${BASE_PATH}/records`, record),
    onSuccess: invalidate,
  });
}

export function useUpdateStockProfileRecord() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: ({ id, record }: { id: number; record: StockBasicProfileInput }) =>
      apiPut<StockBasicProfileRecord>(`${BASE_PATH}/records/${id}`, record),
    onSuccess: invalidate,
  });
}

export function useDeleteStockProfileRecord() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: (id: number) => apiDelete<{ success: boolean }>(`${BASE_PATH}/records/${id}`),
    onSuccess: invalidate,
  });
}

export function useEnrichStockProfileRecord() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: ({ code, force = false }: { code: string; force?: boolean }) =>
      apiPost<StockProfileEnrichResponse>(
        `${BASE_PATH}/enrich/${encodeURIComponent(code)}${force ? "?force=true" : ""}`,
        {},
        { timeoutMs: API_TIMEOUTS.EXTERNAL },
      ),
    onSuccess: invalidate,
  });
}

export function useSyncMasterStockProfiles() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: () =>
      apiPost<Record<string, number>>(`${BASE_PATH}/sync-master`, {}, { timeoutMs: API_TIMEOUTS.LONG_RUNNING }),
    onSuccess: invalidate,
  });
}

export function useImportStockProfiles() {
  const invalidate = useInvalidateStockProfileData();
  return useMutation({
    mutationFn: (request: StockProfileImportFileRequest) =>
      apiPost<StockProfileImportResponse>(
        `${BASE_PATH}/records/import`,
        request,
        { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
      ),
    onSuccess: invalidate,
  });
}
