import { useInfiniteQuery, useMutation, useQuery } from "@tanstack/react-query";
import { API_TIMEOUTS } from "../client";
import {
  asApiModel,
  openApiDelete,
  openApiGet,
  openApiPost,
} from "../openapiClient";
import { queryKeys } from "../queryKeys";
import type { DailyReviewHistoryItem, DailyReviewRequest, DailyReviewResult } from "../../types/dailyReview";
import type {
  AnalysisHistoryItem,
  AnalysisResult,
  AtlasCatalog,
  AtlasChain,
  IndustryChainHistoryItem,
  IndustryChainResult,
  PushRequest,
  PushResponse,
} from "../../types/stock";

export function useInfiniteDailyReviewHistory(pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.dailyReviewHistory(pageSize),
    queryFn: ({ pageParam }) => openApiGet("/api/daily-review/history", {
      query: { limit: pageSize, offset: pageParam },
    }),
    select: (data) => ({
      ...data,
      pages: data.pages.map(asApiModel<DailyReviewHistoryItem[]>()),
    }),
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
    queryFn: () => openApiGet("/api/daily-review/{date}", {
      path: { date },
    }),
    select: asApiModel<DailyReviewResult>(),
    enabled: !!date,
    staleTime: 5 * 60 * 1000,
  });
}

export function useGenerateDailyReview() {
  return useMutation({
    mutationFn: (request: DailyReviewRequest) => openApiPost("/api/daily-review/generate", {
      body: request,
      options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
    }).then(asApiModel<DailyReviewResult>()),
  });
}

export function useDeleteDailyReview() {
  return useMutation({
    mutationFn: (date: string) => openApiDelete("/api/daily-review/{date}", {
      path: { date },
    }),
  });
}

export function usePush() {
  return useMutation({
    mutationFn: (request: PushRequest) => openApiPost("/api/push", {
      body: request,
      options: { timeoutMs: API_TIMEOUTS.EXTERNAL },
    }).then(asApiModel<PushResponse>()),
  });
}

export function useInfiniteAllAnalysisHistory(pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.analysisHistory(pageSize),
    queryFn: ({ pageParam }) => openApiGet("/api/analysis/history/all", {
      query: { limit: pageSize, offset: pageParam },
    }),
    select: (data) => ({
      ...data,
      pages: data.pages.map(asApiModel<AnalysisHistoryItem[]>()),
    }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, pages) => (
      lastPage.length < pageSize
        ? undefined
        : pages.reduce((count, page) => count + page.length, 0)
    ),
    staleTime: 5 * 60 * 1000,
  });
}

export function useAnalysisHistorySnapshot(code: string, date: string) {
  return useQuery({
    queryKey: queryKeys.workflows.analysisHistorySnapshot(code, date),
    queryFn: () => openApiGet("/api/analysis/{code}/history/{date}", {
      path: { code, date },
    }),
    select: asApiModel<AnalysisResult>(),
    enabled: !!code && !!date,
    staleTime: Number.POSITIVE_INFINITY,
  });
}

export function useDeleteAnalysisHistory() {
  return useMutation({
    mutationFn: ({ code, date }: { code: string; date: string }) => openApiDelete(
      "/api/analysis/{code}/history/{date}",
      { path: { code, date } },
    ),
  });
}

export function useInfiniteIndustryChainHistory(name = "", pageSize = 50) {
  return useInfiniteQuery({
    queryKey: queryKeys.workflows.industryChainHistory(name, pageSize),
    queryFn: ({ pageParam }) => openApiGet("/api/industry-chain/history", {
      query: { name: name || undefined, limit: pageSize, offset: pageParam },
    }),
    select: (data) => ({
      ...data,
      pages: data.pages.map(asApiModel<IndustryChainHistoryItem[]>()),
    }),
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
    queryFn: () => openApiGet("/api/industry-chain/{name}/latest", {
      path: { name },
    }),
    enabled: !!name,
    staleTime: 0,
  });
}

export function useIndustryChainAtlasCatalog() {
  return useQuery({
    queryKey: queryKeys.workflows.industryChainAtlasCatalog,
    queryFn: () => openApiGet("/api/industry-chain/atlas/chains"),
    select: asApiModel<AtlasCatalog>(),
    staleTime: 5 * 60 * 1000,
  });
}

export function useIndustryChainAtlasChain(slug: string) {
  return useQuery({
    queryKey: queryKeys.workflows.industryChainAtlasChain(slug),
    queryFn: () => openApiGet("/api/industry-chain/atlas/chains/{slug}", {
      path: { slug },
    }),
    select: asApiModel<AtlasChain>(),
    enabled: !!slug,
    staleTime: 5 * 60 * 1000,
  });
}

export function useImportIndustryChainAtlas() {
  return useMutation({
    mutationFn: (request: { content: string; overwrite?: boolean }) => openApiPost(
      "/api/industry-chain/atlas/import",
      {
        body: request,
        options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
      },
    ).then(asApiModel<AtlasChain[]>()),
  });
}

export function useMineIndustryChainAtlas() {
  return useMutation({
    mutationFn: (request: { name: string; archive_id?: string }) => openApiPost(
      "/api/industry-chain/atlas/mine",
      {
        body: request,
        options: { timeoutMs: API_TIMEOUTS.LONG_RUNNING },
      },
    ).then(asApiModel<AtlasChain>()),
  });
}

export function useDeleteIndustryChainAtlasChain() {
  return useMutation({
    mutationFn: (slug: string) => openApiDelete("/api/industry-chain/atlas/chains/{slug}", {
      path: { slug },
    }),
  });
}

export function useIndustryChainArchive() {
  return useMutation({
    mutationFn: ({ name, archiveId }: { name: string; archiveId: string }) => openApiGet(
      "/api/industry-chain/{name}/archive/{archive_id}",
      { path: { name, archive_id: archiveId } },
    ).then(asApiModel<IndustryChainResult>()),
  });
}

export function useDeleteIndustryChainArchive() {
  return useMutation({
    mutationFn: ({ name, archiveId }: { name: string; archiveId: string }) => openApiDelete(
      "/api/industry-chain/{name}/archive/{archive_id}",
      { path: { name, archive_id: archiveId } },
    ),
  });
}
