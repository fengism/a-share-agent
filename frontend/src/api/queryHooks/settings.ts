import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "../client";
import { createInviteApi, listInvitesApi, revokeInviteApi } from "../auth";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import type { InviteItem } from "../../types/auth";
import type { BotAdminJob, BotAdminJobsResponse, ConfigData, ConfigUpdate } from "../../types/settings";

export function useConfig() {
  return useQuery({
    queryKey: queryKeys.settings.config,
    queryFn: () => apiGet<ConfigData>("/config"),
    staleTime: QUERY_CACHE_POLICIES.settingsConfig.staleMs,
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
    queryFn: () => apiGet<BotAdminJobsResponse>(
      "/bot/jobs",
      { status: "failed", limit: 50 },
    ),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.settingsBotJobs.staleMs,
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
    queryFn: () => listInvitesApi(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.settingsInvites.staleMs,
  });
}

export function useCreateInvite() {
  return useMutation({ mutationFn: (expiresInDays?: number) => createInviteApi(expiresInDays) });
}

export function useRevokeInvite() {
  return useMutation({ mutationFn: (code: string) => revokeInviteApi(code) });
}
