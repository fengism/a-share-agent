import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDelete, apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";
import type {
  PortfolioPosition,
  PortfolioPositionCreate,
  PortfolioResponse,
} from "../../types/portfolio";

export function usePortfolio() {
  return useQuery({
    queryKey: queryKeys.portfolio,
    queryFn: ({ signal }) => apiGet<PortfolioResponse>("/portfolio", undefined, { signal }),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

export function useAddPortfolioPosition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (position: PortfolioPositionCreate) =>
      apiPost<PortfolioPosition>("/portfolio", position),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}

export function useDeletePortfolioPosition() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (positionId: number) =>
      apiDelete<{ deleted: boolean }>(`/portfolio/${positionId}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.portfolio }),
  });
}
