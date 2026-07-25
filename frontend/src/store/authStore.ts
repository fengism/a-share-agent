import { create } from "zustand";
import type { AuthUser } from "../types/auth";
import { getToken, setToken, setUnauthorizedHandler } from "../api/authToken";
import { loginApi, registerApi, logoutApi, meApi } from "../api/auth";

interface AuthState {
  user: AuthUser | null;
  /** True once the initial token-validation (/me) has completed. */
  bootstrapped: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string, inviteCode?: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Clear local session without hitting the API (used on 401 expiry). */
  clearLocal: () => void;
  /** Re-fetch the current user (e.g. after a forced password change). */
  refreshUser: () => Promise<void>;
  /** Validate a persisted token on app start and load the user. */
  bootstrap: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  bootstrapped: false,

  login: async (username, password) => {
    const res = await loginApi({ username, password });
    setToken(res.token);
    set({ user: res.user });
  },

  register: async (username, password, inviteCode) => {
    const res = await registerApi({
      username,
      password,
      invite_code: inviteCode || undefined,
    });
    setToken(res.token);
    set({ user: res.user });
  },

  logout: async () => {
    try {
      await logoutApi();
    } catch {
      /* best-effort: revoke server session, but always clear locally */
    }
    setToken(null);
    set({ user: null });
  },

  clearLocal: () => {
    setToken(null);
    set({ user: null });
  },

  refreshUser: async () => {
    const user = await meApi();
    set({ user });
  },

  bootstrap: async () => {
    if (!getToken()) {
      set({ bootstrapped: true });
      return;
    }
    try {
      const user = await meApi();
      set({ user, bootstrapped: true });
    } catch {
      setToken(null);
      set({ user: null, bootstrapped: true });
    }
  },
}));

// Expired/invalid session on any authenticated request → drop local auth.
// RequireAuth then redirects to /login on the next render.
setUnauthorizedHandler(() => {
  useAuthStore.getState().clearLocal();
});
