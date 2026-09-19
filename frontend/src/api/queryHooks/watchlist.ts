import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import { usePageVisibility } from "../../hooks/usePageVisibility";
import type {
  WatchlistAlert,
  WatchlistAlertCreate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistMarket,
  WatchlistResponse,
} from "../../types/watchlist";

export function useWatchlist() {
  const isTradingSession = useAStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: () => apiGet<WatchlistResponse>("/watchlist"),
    staleTime: QUERY_CACHE_POLICIES.watchlistRealtime.staleMs,
    refetchInterval: isTradingSession && isVisible ? QUERY_CACHE_POLICIES.watchlistRealtime.pollMs : false,
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

type DeleteWatchlistItemInput = string | { stockCode: string; market?: WatchlistMarket };

export function useDeleteWatchlistItem() {
  return useWatchlistMutation((input: DeleteWatchlistItemInput) => {
    const stockCode = typeof input === "string" ? input : input.stockCode;
    const market = typeof input === "string" ? undefined : input.market;
    const query = market === "hk" ? "?market=hk" : "";
    return apiDelete(`/watchlist/${encodeURIComponent(stockCode)}${query}`);
  });
}

export function useAddWatchlistAlert() {
  return useWatchlistMutation(({ stockCode, request }: { stockCode: string; request: WatchlistAlertCreate }) =>
    apiPost<WatchlistAlert>(`/watchlist/${encodeURIComponent(stockCode)}/alerts`, request));
}

export function useDeleteWatchlistAlert() {
  return useWatchlistMutation((alertId: number) => apiDelete(`/watchlist/alerts/${alertId}`));
}
