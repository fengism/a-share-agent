import { getCsrfToken, getToken, notifyUnauthorized } from "./authToken";
import { parseApiError } from "./errors";

const BASE_URL = "/api";
const isDev = import.meta.env.DEV;

export const API_TIMEOUTS = {
  DEFAULT: 15_000,
  EXTERNAL: 120_000,
  LONG_RUNNING: 300_000,
} as const;

export interface ApiRequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

export type ApiQueryParams = Record<string, string | number | boolean | null | undefined>;

export class ApiTimeoutError extends Error {
  constructor(timeoutMs: number) {
    super(`请求超时（${Math.ceil(timeoutMs / 1000)} 秒）`);
    this.name = "ApiTimeoutError";
  }
}

export class ApiError extends Error {
  readonly status: number;
  readonly path: string;
  readonly code?: string;
  readonly requestId?: string;
  readonly errorId?: string;

  constructor(
    status: number,
    path: string,
    message: string,
    metadata: { code?: string; requestId?: string; errorId?: string } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.path = path;
    this.code = metadata.code;
    this.requestId = metadata.requestId;
    this.errorId = metadata.errorId;
  }
}

async function apiRequest<T>(
  method: string,
  path: string,
  body?: unknown,
  params?: ApiQueryParams,
  options: ApiRequestOptions = {},
): Promise<T> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }

  const fullUrl = url.toString();
  if (isDev) console.log(`[API] ${method} ${fullUrl}`);
  const startTime = performance.now();

  const token = getToken();
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    const csrfToken = getCsrfToken();
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
  }

  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? API_TIMEOUTS.DEFAULT;
  let timedOut = false;
  const abortFromCaller = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) {
    abortFromCaller();
  } else {
    options.signal?.addEventListener("abort", abortFromCaller, { once: true });
  }
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  try {
    const response = await fetch(fullUrl, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: controller.signal,
      credentials: "include",
    });
    const elapsed = Math.round(performance.now() - startTime);

    if (!response.ok) {
      if (response.status === 401) notifyUnauthorized();
      const parsedError = parseApiError(
        await response.json().catch(() => ({})),
        `API error: ${response.status}`,
      );
      if (isDev) console.error(`[API] ${method} ${path} 失败: ${response.status} ${parsedError.message} (${elapsed}ms)`);
      throw new ApiError(response.status, path, parsedError.message, parsedError);
    }

    if (isDev) console.log(`[API] ${method} ${path} 成功 (${elapsed}ms)`);
    return response.json() as Promise<T>;
  } catch (error) {
    if (timedOut) throw new ApiTimeoutError(timeoutMs);
    throw error;
  } finally {
    window.clearTimeout(timer);
    options.signal?.removeEventListener("abort", abortFromCaller);
  }
}

export function apiGet<T>(path: string, params?: ApiQueryParams, options?: ApiRequestOptions): Promise<T> {
  return apiRequest<T>("GET", path, undefined, params, options);
}

export function apiPost<T>(path: string, body?: unknown, options?: ApiRequestOptions): Promise<T> {
  return apiRequest<T>("POST", path, body, undefined, options);
}

export function apiPut<T>(path: string, body?: unknown, options?: ApiRequestOptions): Promise<T> {
  return apiRequest<T>("PUT", path, body, undefined, options);
}

export function apiDelete<T>(path: string, options?: ApiRequestOptions): Promise<T> {
  return apiRequest<T>("DELETE", path, undefined, undefined, options);
}

export async function apiDownload(
  path: string,
  fallbackFilename: string,
  params?: ApiQueryParams,
  options: ApiRequestOptions = {},
): Promise<void> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== "") {
        url.searchParams.set(key, String(value));
      }
    });
  }
  const fullUrl = `${url.pathname}${url.search}`;
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(fullUrl, {
    method: "GET",
    headers,
    credentials: "include",
    signal: options.signal,
  });

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const errorBody = await response.json().catch(() => ({}));
    const parsedError = parseApiError(errorBody, `下载失败: ${response.status}`);
    throw new ApiError(response.status, path, parsedError.message, parsedError);
  }

  const blob = await response.blob();
  let filename = fallbackFilename;
  const disposition = response.headers.get("Content-Disposition");
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
      filename = decodeURIComponent(utf8Match[1]);
    } else {
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match?.[1]) filename = match[1];
    }
  }

  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(blobUrl);
}

export async function apiDownloadPost(
  path: string,
  body: unknown,
  fallbackFilename: string,
  options: ApiRequestOptions = {},
): Promise<void> {
  const url = new URL(`${BASE_URL}${path}`, window.location.origin);
  const fullUrl = `${url.pathname}${url.search}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const csrfToken = getCsrfToken();
  if (csrfToken) headers["X-CSRF-Token"] = csrfToken;

  const response = await fetch(fullUrl, {
    method: "POST",
    headers,
    body: JSON.stringify(body),
    credentials: "include",
    signal: options.signal,
  });

  if (!response.ok) {
    if (response.status === 401) notifyUnauthorized();
    const errorBody = await response.json().catch(() => ({}));
    const parsedError = parseApiError(errorBody, `下载失败: ${response.status}`);
    throw new ApiError(response.status, path, parsedError.message, parsedError);
  }

  const blob = await response.blob();
  let filename = fallbackFilename;
  const disposition = response.headers.get("Content-Disposition");
  if (disposition) {
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
      filename = decodeURIComponent(utf8Match[1]);
    } else {
      const match = disposition.match(/filename="?([^";]+)"?/i);
      if (match?.[1]) filename = match[1];
    }
  }

  const blobUrl = window.URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = blobUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.URL.revokeObjectURL(blobUrl);
}
