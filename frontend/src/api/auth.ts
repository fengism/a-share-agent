import { apiGet, apiPost } from "./client";
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

export function createInviteApi() {
  return apiPost<InviteItem>("/auth/invite");
}

export function listInvitesApi() {
  return apiGet<InviteItem[]>("/auth/invites");
}
