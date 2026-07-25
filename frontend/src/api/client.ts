import { getToken, notifyUnauthorized } from "./authToken";

const BASE_URL = "/api";
const isDev = import.meta.env.DEV;
const REQUEST_TIMEOUT_MS = 15_000;

async function apiRequest<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    });
  }

  const fullUrl = url.toString();
  if (isDev) console.log(`[API] ${method} ${fullUrl}`);
  const startTime = performance.now();

  const token = getToken();
  const headers: Record<string, string> = {};
  if (body) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  try {
    const res = await fetch(fullUrl, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    const elapsed = Math.round(performance.now() - startTime);

  if (!res.ok) {
    // A 401 on a request that carried a token means the session expired/was
    // revoked — drop local auth so the guard redirects to /login. (A 401 on a
    // tokenless request, e.g. a failed login, is just a normal error.)
    if (res.status === 401 && token) notifyUnauthorized();
    const errData = await res.json().catch(() => ({}));
    const errMsg = errData.detail || `API error: ${res.status}`;
    if (isDev) console.error(`[API] ${method} ${path} 失败: ${res.status} ${errMsg} (${elapsed}ms)`);
    throw new Error(errMsg);
  }

  if (isDev) console.log(`[API] ${method} ${path} 成功 (${elapsed}ms)`);
  return res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  return apiRequest<T>("GET", path, undefined, params);
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>("POST", path, body);
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  return apiRequest<T>("PUT", path, body);
}

export async function apiDelete<T>(path: string): Promise<T> {
  return apiRequest<T>("DELETE", path);
}
