import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { API_TIMEOUTS, apiDelete, apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import type { DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult } from "../../types/dailyReview";
import type {
  AnalysisHistoryItem,
  IndustryChainHistoryItem,
  IndustryChainResult,
  PushRequest,
  PushResponse,
} from "../../types/stock";

interface DeleteResponse {
  deleted: boolean;
}

export function useInfiniteDailyReviewHistory(pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.dailyReviewHistory(pageSize),
    queryFn: ({ pageParam, signal }) => apiGet<DailyReviewHistoryItem[]>(
      "/daily-review/history",
      { limit: pageSize, offset: pageParam },
      { signal },
    ),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (
      lastPage.length < pageSize
        ? undefined
        : pages.reduce((count, page) => count + page.length, 0)
    ),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDailyReview(date: string) {
  return useQuery({
    queryKey: queryKeys.workflows.dailyReview(date),
    queryFn: ({ signal }) => apiGet<DailyReviewResult>(`/daily-review/${date}`, undefined, { signal }),
    enabled: !!date,
    staleTime: 5 * 60 * 1000,
  });
}

export function useGenerateDailyReview() {
  return useMutation({
    mutationFn: (req: DailyReviewRequest) => apiPost<DailyReviewResult>("/daily-review/generate", req, { timeoutMs: API_TIMEOUTS.LONG_RUNNING }),
  });
}

export function useDeleteDailyReview() {
  return useMutation({
    mutationFn: (date: string) => apiDelete<DeleteResponse>(
      `/daily-review/${encodeURIComponent(date)}`,
    ),
  });
}

export function usePush() {
  return useMutation({
    mutationFn: (req: PushRequest) =>
      apiPost<PushResponse>("/push", req, { timeoutMs: API_TIMEOUTS.EXTERNAL }),
  });
}

export function useInfiniteAllAnalysisHistory(pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.analysisHistory(pageSize),
    queryFn: ({ pageParam, signal }) => apiGet<AnalysisHistoryItem[]>(
      "/analysis/history/all",
      { limit: pageSize, offset: pageParam },
      { signal },
    ),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (
      lastPage.length < pageSize
        ? undefined
        : pages.reduce((count, page) => count + page.length, 0)
    ),
    staleTime: 5 * 60 * 1000,
  });
}

export function useDeleteAnalysisHistory() {
  return useMutation({
    mutationFn: ({ code, date }: { code: string; date: string }) => apiDelete<DeleteResponse>(
      `/analysis/${encodeURIComponent(code)}/history/${encodeURIComponent(date)}`,
    ),
  });
}

export function useInfiniteIndustryChainHistory(name = "", pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.industryChainHistory(name, pageSize),
    queryFn: ({ pageParam, signal }) => apiGet<IndustryChainHistoryItem[]>(
      "/industry-chain/history",
      { name: name || undefined, limit: pageSize, offset: pageParam },
      { signal },
    ),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (
      lastPage.length < pageSize
        ? undefined
        : pages.reduce((count, page) => count + page.length, 0)
    ),
    staleTime: 0,
  });
}

export function useIndustryChainLatest(name: string) {
  return useQuery({
    queryKey: queryKeys.workflows.industryChainLatest(name),
    queryFn: ({ signal }) => apiGet<{ archive_id: string; saved_at: string }>(
      `/industry-chain/${encodeURIComponent(name)}/latest`,
      undefined,
      { signal },
    ),
    enabled: !!name,
    staleTime: 0,
  });
}

export function useIndustryChainArchive() {
  return useMutation({
    mutationFn: ({ name, archiveId }: { name: string; archiveId: string }) =>
      apiGet<IndustryChainResult>(
        `/industry-chain/${encodeURIComponent(name)}/archive/${archiveId}`,
      ),
  });
}

export function useDeleteIndustryChainArchive() {
  return useMutation({
    mutationFn: ({ name, archiveId }: { name: string; archiveId: string }) => apiDelete<DeleteResponse>(
      `/industry-chain/${encodeURIComponent(name)}/archive/${encodeURIComponent(archiveId)}`,
    ),
  });
}
