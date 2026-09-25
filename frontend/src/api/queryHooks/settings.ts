import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiPost, apiPut } from "../client";
import {
  cleanupExpiredInvitesApi,
  createInviteApi,
  deleteUserApi,
  fetchLoginAuditLogsApi,
  listInvitesApi,
  listUsersApi,
  revokeInviteApi,
  revokeUserSessionsApi,
  updateUserMustChangePasswordApi,
  updateUserRoleApi,
  updateUserStatusApi,
} from "../auth";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { queryKeys } from "../queryKeys";
import type { AdminUserItem, InviteItem, LoginAuditLogsResponse } from "../../types/auth";
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

export function useAdminUsers(enabled: boolean) {
  return useQuery<AdminUserItem[]>({
    queryKey: queryKeys.settings.users,
    queryFn: () => listUsersApi(),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.settingsUsers.staleMs,
  });
}

export function useUpdateUserStatus() {
  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: number; isActive: boolean }) =>
      updateUserStatusApi(userId, isActive),
  });
}

export function useUpdateUserRole() {
  return useMutation({
    mutationFn: ({ userId, isAdmin }: { userId: number; isAdmin: boolean }) =>
      updateUserRoleApi(userId, isAdmin),
  });
}

export function useDeleteUser() {
  return useMutation({
    mutationFn: (userId: number) => deleteUserApi(userId),
  });
}

export function useRevokeUserSessions() {
  return useMutation({
    mutationFn: (userId: number) => revokeUserSessionsApi(userId),
  });
}

export function useUpdateUserMustChangePassword() {
  return useMutation({
    mutationFn: ({ userId, mustChangePassword }: { userId: number; mustChangePassword: boolean }) =>
      updateUserMustChangePasswordApi(userId, mustChangePassword),
  });
}

export function useCleanupExpiredInvites() {
  return useMutation({
    mutationFn: () => cleanupExpiredInvitesApi(),
  });
}

export function useLoginAuditLogs(
  params?: { limit?: number; offset?: number; status?: string; username?: string },
  enabled = true,
) {
  return useQuery<LoginAuditLogsResponse>({
    queryKey: queryKeys.settings.auditLogs(params),
    queryFn: ({ signal }) => fetchLoginAuditLogsApi(params, signal),
    enabled,
    staleTime: QUERY_CACHE_POLICIES.settingsAuditLogs.staleMs,
  });
}
