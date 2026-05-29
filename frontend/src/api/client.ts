const BASE_URL = "/api";
const isDev = import.meta.env.DEV;

export async function apiGet<T>(path: string, params?: Record<string, string>): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([k, v]) => {
      if (v !== undefined && v !== "") url.searchParams.set(k, v);
    });
  }

  const fullUrl = url.toString();
  if (isDev) console.log(`[API] GET ${fullUrl}`);
  const startTime = performance.now();

  const res = await fetch(fullUrl);
  const elapsed = Math.round(performance.now() - startTime);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const errMsg = body.detail || `API error: ${res.status}`;
    if (isDev) console.error(`[API] GET ${path} 失败: ${res.status} ${errMsg} (${elapsed}ms)`);
    throw new Error(errMsg);
  }

  if (isDev) console.log(`[API] GET ${path} 成功 (${elapsed}ms)`);
  return res.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  if (isDev) console.log(`[API] POST ${BASE_URL}${path}`);
  const startTime = performance.now();

  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const elapsed = Math.round(performance.now() - startTime);

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const errMsg = data.detail || `API error: ${res.status}`;
    if (isDev) console.error(`[API] POST ${path} 失败: ${res.status} ${errMsg} (${elapsed}ms)`);
    throw new Error(errMsg);
  }

  if (isDev) console.log(`[API] POST ${path} 成功 (${elapsed}ms)`);
  return res.json();
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
  if (isDev) console.log(`[API] PUT ${BASE_URL}${path}`);
  const startTime = performance.now();

  const res = await fetch(`${BASE_URL}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const elapsed = Math.round(performance.now() - startTime);

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    const errMsg = data.detail || `API error: ${res.status}`;
    if (isDev) console.error(`[API] PUT ${path} 失败: ${res.status} ${errMsg} (${elapsed}ms)`);
    throw new Error(errMsg);
  }

  if (isDev) console.log(`[API] PUT ${path} 成功 (${elapsed}ms)`);
  return res.json();
}
