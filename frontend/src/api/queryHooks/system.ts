import { useMutation, useQuery } from "@tanstack/react-query";
import { apiGet, apiPost } from "../client";
import { queryKeys } from "../queryKeys";

export interface VersionCheckData {
  current_version: string;
  latest_version: string | null;
  update_available: boolean;
}

export function useVersionCheck(options?: { pollMs?: number }) {
  return useQuery({
    queryKey: queryKeys.system.version,
    queryFn: ({ signal }) =>
      apiGet<VersionCheckData>("/system/version", undefined, { signal }),
    staleTime: 5 * 60_000,
    refetchInterval: options?.pollMs ?? 10 * 60_000,
    retry: false,
  });
}

export function useTriggerUpdate() {
  return useMutation({
    mutationFn: () => apiPost<{ status: string }>("/system/update"),
  });
}
