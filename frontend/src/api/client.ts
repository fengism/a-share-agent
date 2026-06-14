const BASE_URL = "/api";
const isDev = import.meta.env.DEV;

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

  const res = await fetch(fullUrl, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const elapsed = Math.round(performance.now() - startTime);

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    const errMsg = errData.detail || `API error: ${res.status}`;
    if (isDev) console.error(`[API] ${method} ${path} 失败: ${res.status} ${errMsg} (${elapsed}ms)`);
    throw new Error(errMsg);
  }

  if (isDev) console.log(`[API] ${method} ${path} 成功 (${elapsed}ms)`);
  return res.json();
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
