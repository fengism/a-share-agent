import { create } from "zustand";
import type { AuthUser } from "../types/auth";
import { setToken, setUnauthorizedHandler } from "../api/authToken";
import { loginApi, registerApi, logoutApi, meApi } from "../api/auth";
import { setActiveUserScope } from "./userScope";

interface AuthState {
  user: AuthUser | null;
  /** True once the initial token-validation (/me) has completed. */
  bootstrapped: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (
    username: string,
    password: string,
    inviteCode?: string,
    setupToken?: string,
  ) => Promise<void>;
  logout: () => Promise<void>;
  /** Clear local session without hitting the API (used on 401 expiry). */
  clearLocal: () => void;
  /** Re-fetch the current user (e.g. after a forced password change). */
  refreshUser: () => Promise<void>;
  /** Validate the HttpOnly cookie session on app start and load the user. */
  bootstrap: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  bootstrapped: false,

  login: async (username, password) => {
    const res = await loginApi({ username, password });
    setToken(null);
    setActiveUserScope(res.user.id);
    set({ user: res.user });
  },

  register: async (username, password, inviteCode, setupToken) => {
    const res = await registerApi({
      username,
      password,
      invite_code: inviteCode || undefined,
      setup_token: setupToken || undefined,
    });
    setToken(null);
    setActiveUserScope(res.user.id);
    set({ user: res.user });
  },

  logout: async () => {
    try {
      await logoutApi();
    } catch {
      /* best-effort: revoke server session, but always clear locally */
    }
    setToken(null);
    setActiveUserScope(null);
    set({ user: null });
  },

  clearLocal: () => {
    setToken(null);
    setActiveUserScope(null);
    set({ user: null });
  },

  refreshUser: async () => {
    const user = await meApi();
    setActiveUserScope(user.id);
    set({ user });
  },

  bootstrap: async () => {
    try {
      const user = await meApi();
      setActiveUserScope(user.id);
      set({ user, bootstrapped: true });
    } catch {
      setToken(null);
      setActiveUserScope(null);
      set({ user: null, bootstrapped: true });
    }
  },
}));

// Expired/invalid session on any authenticated request → drop local auth.
// RequireAuth then redirects to /login on the next render.
setUnauthorizedHandler(() => {
  useAuthStore.getState().clearLocal();
});
