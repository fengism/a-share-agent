import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import { useAStockTradingSession } from "../../hooks/useAStockTradingSession";
import { useHKStockTradingSession } from "../../hooks/useHKStockTradingSession";
import { usePageVisibility } from "../../hooks/usePageVisibility";
import { isHkStockCode } from "../../utils/stockLinks";
import type {
  WatchlistAlert,
  WatchlistAlertCreate,
  WatchlistItem,
  WatchlistItemCreate,
  WatchlistMarket,
  WatchlistResponse,
} from "../../types/watchlist";

export function useWatchlist() {
  const isAShareSession = useAStockTradingSession();
  const isHKShareSession = useHKStockTradingSession();
  const isVisible = usePageVisibility();
  return useQuery({
    queryKey: queryKeys.watchlist,
    queryFn: () => apiGet<WatchlistResponse>("/watchlist"),
    staleTime: QUERY_CACHE_POLICIES.watchlistRealtime.staleMs,
    // A 股盘中常规刷新；港股尾盘（11:30–12:05、15:10–16:10）A 股已收盘，
    // 只要自选里含港股就继续刷新，避免港股价格冻结。
    refetchInterval: (query) => {
      if (!isVisible) return false;
      const hasHkItems = (query.state.data?.items ?? []).some((item) => item.market === "hk");
      const active = isAShareSession || (hasHkItems && isHKShareSession);
      return active ? QUERY_CACHE_POLICIES.watchlistRealtime.pollMs : false;
    },
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
  return useWatchlistMutation((request: WatchlistItemCreate) => {
    // 港股代码（1-5 位）与 A 股（6 位）天然互斥，缺省时按代码判定市场，避免把港股当 A 股提交。
    const market = request.market ?? (isHkStockCode(request.stock_code) ? "hk" : "cn");
    return apiPost<WatchlistItem>("/watchlist", { ...request, market });
  });
}

type DeleteWatchlistItemInput = string | { stockCode: string; market?: WatchlistMarket };

export function useDeleteWatchlistItem() {
  return useWatchlistMutation((input: DeleteWatchlistItemInput) => {
    const stockCode = typeof input === "string" ? input : input.stockCode;
    const market = typeof input === "string" ? undefined : input.market;
    const resolvedMarket = market ?? (isHkStockCode(stockCode) ? "hk" : "cn");
    const query = resolvedMarket === "hk" ? "?market=hk" : "";
    return apiDelete(`/watchlist/${encodeURIComponent(stockCode)}${query}`);
  });
}

export function useAddWatchlistAlert() {
  return useWatchlistMutation(({ stockCode, request }: { stockCode: string; request: WatchlistAlertCreate }) => {
    const market = request.market ?? (isHkStockCode(stockCode) ? "hk" : "cn");
    return apiPost<WatchlistAlert>(`/watchlist/${encodeURIComponent(stockCode)}/alerts`, { ...request, market });
  });
}

export function useDeleteWatchlistAlert() {
  return useWatchlistMutation((alertId: number) => apiDelete(`/watchlist/alerts/${alertId}`));
}
