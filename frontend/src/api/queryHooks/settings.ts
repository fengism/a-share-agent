import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "../client";
import { createInviteApi, listInvitesApi, revokeInviteApi } from "../auth";
import { queryKeys } from "../queryKeys";
import type { InviteItem } from "../../types/auth";
import type { BotAdminJob, BotAdminJobsResponse, ConfigData, ConfigUpdate } from "../../types/settings";

export function useConfig() {
  return useQuery({
    queryKey: queryKeys.settings.config,
    queryFn: ({ signal }) => apiGet<ConfigData>("/config", undefined, { signal }),
    staleTime: 30 * 1000,
  });
}

export function useUpdateConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: ConfigUpdate) => apiPut<ConfigData>("/config", patch),
    onSuccess: (data) => queryClient.setQueryData(queryKeys.settings.config, data),
  });
}

export function useBotJobs(enabled: boolean) {
  return useQuery<BotAdminJobsResponse>({
    queryKey: queryKeys.settings.failedBotJobs,
    queryFn: ({ signal }) => apiGet<BotAdminJobsResponse>(
      "/bot/jobs",
      { status: "failed", limit: 50 },
      { signal },
    ),
    enabled,
    staleTime: 10 * 1000,
  });
}

export function useRetryBotJob() {
  return useMutation({
    mutationFn: (jobId: string) => apiPost<BotAdminJob>(`/bot/jobs/${jobId}/retry`),
  });
}

export function useInvites(enabled: boolean) {
  return useQuery<InviteItem[]>({
    queryKey: queryKeys.settings.invites,
    queryFn: ({ signal }) => listInvitesApi(signal),
    enabled,
    staleTime: 30 * 1000,
  });
}

export function useCreateInvite() {
  return useMutation({ mutationFn: (expiresInDays?: number) => createInviteApi(expiresInDays) });
}

export function useRevokeInvite() {
  return useMutation({ mutationFn: (code: string) => revokeInviteApi(code) });
}
