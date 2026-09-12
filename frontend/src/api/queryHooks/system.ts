import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { components } from "../generated/schema";
import { apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";

export type VersionCheckData = components["schemas"]["VersionCheckResponse"];
export type UpdateStatusData = components["schemas"]["UpdateStatusResponse"];

export function useVersionCheck(options?: { pollMs?: number | false }) {
  const pollMs = options?.pollMs ?? false;
  return useQuery({
    queryKey: queryKeys.system.version,
    queryFn: ({ signal }) =>
      apiGet<VersionCheckData>("/system/version", undefined, { signal }),
    enabled: pollMs !== false,
    staleTime: 5 * 60_000,
    // 默认不自动查询；更新触发后由 pollMs 开启轮询。
    refetchInterval: pollMs,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useUpdateStatus(options?: { enabled?: boolean; pollMs?: number | false }) {
  return useQuery({
    queryKey: queryKeys.system.updateStatus,
    queryFn: ({ signal }) =>
      apiGet<UpdateStatusData>("/system/update/status", undefined, { signal }),
    enabled: options?.enabled ?? false,
    refetchInterval: options?.pollMs ?? false,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useTriggerUpdate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => apiPost<UpdateStatusData>("/system/update"),
    onSuccess: (status) => {
      queryClient.setQueryData(queryKeys.system.updateStatus, status);
    },
  });
}
