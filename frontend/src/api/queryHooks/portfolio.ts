import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost, apiPut } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import type { components } from "../generated/schema";
import { queryKeys } from "../queryKeys";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import { usePageVisibility } from "../../hooks/usePageVisibility";
import type {
  PortfolioAccountSettings,
  PortfolioAccountSettingsUpdate,
  PortfolioResponse,
  PortfolioTransaction,
  PortfolioTransactionCreate,
  PortfolioTransactionPreview,
} from "../../types/portfolio";

type DeleteResponse = components["schemas"]["DeleteResponse"];

export function usePortfolio() {
  const isTradingSession = useAStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: () => apiGet<PortfolioResponse>("/portfolio"),
    staleTime: QUERY_CACHE_POLICIES.portfolioRealtime.staleMs,
    refetchInterval: isTradingSession && isVisible ? QUERY_CACHE_POLICIES.portfolioRealtime.pollMs : false,
  });
}

export function useCreatePortfolioTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (transaction: PortfolioTransactionCreate) =>
      apiPost<PortfolioTransaction>("/portfolio/transactions", transaction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}

export function useUpdatePortfolioSettings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (settings: PortfolioAccountSettingsUpdate) =>
      apiPut<PortfolioAccountSettings>("/portfolio/settings", settings),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}

export function usePreviewPortfolioTransaction() {
  return useMutation({
    mutationFn: (transaction: PortfolioTransactionCreate) =>
      apiPost<PortfolioTransactionPreview>("/portfolio/transactions/preview", transaction),
  });
}

export function usePreviewPortfolioTransactionUpdate() {
  return useMutation({
    mutationFn: ({
      transactionId,
      transaction,
    }: {
      transactionId: number;
      transaction: PortfolioTransactionCreate;
    }) => apiPost<PortfolioTransactionPreview>(
      `/portfolio/transactions/${transactionId}/preview`,
      transaction,
    ),
  });
}

export function useUpdatePortfolioTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      transactionId,
      transaction,
    }: {
      transactionId: number;
      transaction: PortfolioTransactionCreate;
    }) => apiPut<PortfolioTransaction>(`/portfolio/transactions/${transactionId}`, transaction),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}

export function useDeletePortfolioTransaction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (transactionId: number) =>
      apiDelete<DeleteResponse>(`/portfolio/transactions/${transactionId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}
