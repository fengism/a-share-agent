import { apiGet, apiPost, apiPut, apiDelete } from "./client";
import type {
  AdminAuditActionsResponse,
  AdminUserItem,
  AuthResponse,
  AuthUser,
  InviteItem,
  LoginAuditLogsResponse,
  SessionsResponse,
} from "../types/auth";

export function registerApi(body: {
  username: string;
  password: string;
  invite_code?: string;
  setup_token?: string;
}) {
  return apiPost<AuthResponse>("/auth/register", body);
}

export function loginApi(body: { username: string; password: string }) {
  return apiPost<AuthResponse>("/auth/login", body);
}

export function logoutApi() {
  return apiPost<{ ok: boolean }>("/auth/logout");
}

export function changePasswordApi(body: { old_password: string; new_password: string }) {
  return apiPost<{ ok: boolean; revoked_sessions?: number }>("/auth/change-password", body);
}

export function adminResetLinkApi(body: { username: string; expires_in_hours?: number }) {
  return apiPost<{ username: string; token: string; expires_at: string }>("/auth/admin/reset-link", body);
}

export function resetPasswordApi(body: { token: string; new_password: string }) {
  return apiPost<{ ok: boolean }>("/auth/reset-password", body);
}

export function meApi() {
  return apiGet<AuthUser>("/auth/me");
}

export function needsSetupApi() {
  return apiGet<{ needs_setup: boolean; requires_setup_token?: boolean }>("/auth/needs-setup");
}

export function createInviteApi(expiresInDays?: number) {
  return apiPost<InviteItem>("/auth/invite", { expires_in_days: expiresInDays ?? null });
}

export function listInvitesApi(signal?: AbortSignal) {
  return apiGet<InviteItem[]>("/auth/invites", undefined, { signal });
}

export function revokeInviteApi(code: string) {
  return apiDelete<{ ok: boolean }>(`/auth/invite/${encodeURIComponent(code)}`);
}

export function cleanupExpiredInvitesApi() {
  return apiPost<{ ok: boolean; cleaned_count: number }>("/auth/invites/cleanup-expired");
}

export function listUsersApi(signal?: AbortSignal) {
  return apiGet<AdminUserItem[]>("/auth/admin/users", undefined, { signal });
}

export function updateUserStatusApi(userId: number, isActive: boolean) {
  return apiPut<AdminUserItem>(`/auth/admin/users/${userId}/status`, { is_active: isActive });
}

export function updateUserRoleApi(userId: number, isAdmin: boolean) {
  return apiPut<AdminUserItem>(`/auth/admin/users/${userId}/role`, { is_admin: isAdmin });
}

export function updateUserMustChangePasswordApi(userId: number, mustChangePassword: boolean) {
  return apiPost<AdminUserItem>(`/auth/admin/users/${userId}/must-change-password`, {
    must_change_password: mustChangePassword,
  });
}

export function deleteUserApi(userId: number) {
  return apiDelete<{ ok: boolean }>(`/auth/admin/users/${userId}`);
}

export function revokeUserSessionsApi(userId: number) {
  return apiPost<{ ok: boolean; revoked_sessions: number }>(`/auth/admin/users/${userId}/revoke-sessions`);
}

export function fetchSessionsApi(signal?: AbortSignal) {
  return apiGet<SessionsResponse>("/auth/sessions", undefined, { signal });
}

export function revokeSessionApi(sessionId: string) {
  return apiDelete<{ ok: boolean }>(`/auth/sessions/${encodeURIComponent(sessionId)}`);
}

export function fetchAdminAuditActionsApi(
  params?: { limit?: number; offset?: number; action?: string; actor_username?: string },
  signal?: AbortSignal,
) {
  return apiGet<AdminAuditActionsResponse>("/auth/admin/audit-actions", params, { signal });
}

/** 当前登录用户自己的登录记录（只返回本人 user_id 的记录）。 */
export function fetchMyLoginAuditLogsApi(
  params?: { limit?: number; offset?: number; status?: string },
  signal?: AbortSignal,
) {
  return apiGet<LoginAuditLogsResponse>("/auth/audit-logs/me", params, { signal });
}

export function fetchLoginAuditLogsApi(
  params?: { limit?: number; offset?: number; status?: string; username?: string },
  signal?: AbortSignal,
) {
  return apiGet<LoginAuditLogsResponse>("/auth/admin/audit-logs", params, { signal });
}
