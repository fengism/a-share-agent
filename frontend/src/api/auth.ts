import { apiGet, apiPost, apiDelete } from "./client";
import type { AuthResponse, AuthUser, InviteItem } from "../types/auth";

export function registerApi(body: { username: string; password: string; invite_code?: string }) {
  return apiPost<AuthResponse>("/auth/register", body);
}

export function loginApi(body: { username: string; password: string }) {
  return apiPost<AuthResponse>("/auth/login", body);
}

export function logoutApi() {
  return apiPost<{ ok: boolean }>("/auth/logout");
}

export function meApi() {
  return apiGet<AuthUser>("/auth/me");
}

export function needsSetupApi() {
  return apiGet<{ needs_setup: boolean }>("/auth/needs-setup");
}

export function createInviteApi(expiresInDays?: number) {
  return apiPost<InviteItem>("/auth/invite", { expires_in_days: expiresInDays ?? null });
}

export function listInvitesApi() {
  return apiGet<InviteItem[]>("/auth/invites");
}

export function revokeInviteApi(code: string) {
  return apiDelete<{ ok: boolean }>(`/auth/invite/${encodeURIComponent(code)}`);
}
