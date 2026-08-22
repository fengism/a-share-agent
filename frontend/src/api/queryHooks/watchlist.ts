import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import type {
  WatchlistAlert,
  WatchlistAlertCreate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistResponse,
} from "../../types/watchlist";

export function useWatchlist() {
  const isTradingSession = useAStockTradingSession();
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: () => apiGet<WatchlistResponse>("/watchlist"),
    staleTime: 30_000,
    refetchInterval: isTradingSession ? 30_000 : false,
  });
}

function useWatchlistMutation<Variables, Result>(mutationFn: (variables: Variables) => Promise<Result>) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.watchlist }),
  });
}

export function useAddWatchlistItem() {
  return useWatchlistMutation((request: WatchlistItemCreate) => apiPost<WatchlistItem>("/watchlist", request));
}

export function useDeleteWatchlistItem() {
  return useWatchlistMutation((stockCode: string) => apiDelete(`/watchlist/${encodeURIComponent(stockCode)}`));
}

export function useAddWatchlistAlert() {
  return useWatchlistMutation(({ stockCode, request }: { stockCode: string; request: WatchlistAlertCreate }) =>
    apiPost<WatchlistAlert>(`/watchlist/${encodeURIComponent(stockCode)}/alerts`, request));
}

export function useDeleteWatchlistAlert() {
  return useWatchlistMutation((alertId: number) => apiDelete(`/watchlist/alerts/${alertId}`));
}
