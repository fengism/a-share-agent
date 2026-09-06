import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";

export interface VersionCheckData {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
}

export function useVersionCheck(options?: { pollMs?: number | false }) {
  return useQuery({
    queryKey: queryKeys.system.version,
    queryFn: ({ signal }) =>
      apiGet<VersionCheckData>("/system/version", undefined, { signal }),
    staleTime: 5 * 60_000,
    // 默认不自动轮询，仅由用户手动"检查更新"触发；
    // 触发更新后的完成检测例外（pollMs），用于轮询新容器版本就绪。
    refetchInterval: options?.pollMs ?? false,
    refetchOnWindowFocus: false,
    retry: false,
  });
}

export function useTriggerUpdate() {
  return useMutation({
    mutationFn: () => apiPost<{ status: string }>("/system/update"),
  });
}
