import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { API_TIMEOUTS, ApiError, ApiTimeoutError, apiGet, apiPost } from "./client";
import { setToken, setUnauthorizedHandler } from "./authToken";

describe("api client request lifecycle", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setToken(null);
    setUnauthorizedHandler(null);
    document.cookie = "a_share_csrf=; Max-Age=0; path=/";
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("keeps screener requests on a five-minute timeout budget", () => {
    expect(API_TIMEOUTS.SCREENER).toBe(300_000);
    expect(API_TIMEOUTS.SCREENER).toBeGreaterThan(API_TIMEOUTS.DEFAULT);
  });

  it("propagates a caller abort signal to the underlying fetch", async () => {
    let fetchSignal: AbortSignal | undefined;
    let resolveFetch: ((value: Response) => void) | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      fetchSignal = init?.signal as AbortSignal;
      return new Promise<Response>((resolve) => {
        resolveFetch = resolve;
      });
    }));

    const caller = new AbortController();
    const request = apiGet<{ ok: boolean }>("/slow", undefined, {
      signal: caller.signal,
      timeoutMs: API_TIMEOUTS.LONG_RUNNING,
    });

    caller.abort();
    expect(fetchSignal?.aborted).toBe(true);

    resolveFetch?.({ ok: true, json: async () => ({ ok: true }) } as Response);
    await expect(request).resolves.toEqual({ ok: true });
  });

  it("uses a per-request timeout and reports it distinctly", async () => {
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      const signal = init?.signal;
      if (!signal) throw new Error("missing fetch signal");
      fetchSignal = signal;
      return new Promise<Response>((_resolve, reject) => {
        signal.addEventListener("abort", () => {
          reject(new DOMException("aborted", "AbortError"));
        }, { once: true });
      });
    }));

    const request = apiGet("/slow", undefined, { timeoutMs: 50 });
    const rejection = expect(request).rejects.toBeInstanceOf(ApiTimeoutError);

    await vi.advanceTimersByTimeAsync(50);

    expect(fetchSignal?.aborted).toBe(true);
    await rejection;
  });

  it("keeps the unauthorized callback behavior", async () => {
    const unauthorized = vi.fn();
    setToken("expired-token");
    setUnauthorizedHandler(unauthorized);
    vi.stubGlobal("fetch", vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({
        code: "auth.session_expired",
        message: "expired",
        request_id: "request-1",
      }),
    } as Response)));

    const request = apiGet("/protected");
    await expect(request).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      path: "/protected",
      message: "expired",
      code: "auth.session_expired",
      requestId: "request-1",
    } satisfies Partial<ApiError>);
    expect(unauthorized).toHaveBeenCalledTimes(1);
  });

  it("includes cookies and the CSRF header on writes", async () => {
    document.cookie = "a_share_csrf=csrf-token; path=/";
    let requestInit: RequestInit | undefined;
    vi.stubGlobal("fetch", vi.fn(async (_url, init) => {
      requestInit = init;
      return { ok: true, json: async () => ({ ok: true }) } as Response;
    }));

    await apiPost("/protected", { value: 1 });

    expect(requestInit?.credentials).toBe("include");
    expect(requestInit?.headers).toMatchObject({ "X-CSRF-Token": "csrf-token" });
  });
});

describe("api client download timeout", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    setToken(null);
    setUnauthorizedHandler(null);
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("aborts a hung PDF download instead of waiting forever", async () => {
    // 回归背景：apiDownload/apiDownloadPost 过去直接用 options.signal（默认 undefined），
    // 后端渲染卡住时 fetch 会一直挂着，用户既等不到结果也无法取消。
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      fetchSignal = init?.signal as AbortSignal;
      // 真实 fetch 在 signal 中止时会 reject；桩也必须这样，否则 pending 永远悬挂。
      return new Promise<Response>((_resolve, reject) => {
        fetchSignal?.addEventListener(
          "abort",
          () => reject(new DOMException("aborted", "AbortError")),
          { once: true },
        );
      });
    }));

    const { apiDownload } = await import("./client");
    const pending = apiDownload("/analysis/123/export-pdf", "report.pdf");
    const assertion = expect(pending).rejects.toBeInstanceOf(ApiTimeoutError);

    await vi.advanceTimersByTimeAsync(API_TIMEOUTS.LONG_RUNNING);
    await assertion;
    expect(fetchSignal?.aborted).toBe(true);
  });

  it("aborts a hung POST download too", async () => {
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      fetchSignal = init?.signal as AbortSignal;
      return new Promise<Response>((_resolve, reject) => {
        fetchSignal?.addEventListener(
          "abort",
          () => reject(new DOMException("aborted", "AbortError")),
          { once: true },
        );
      });
    }));

    const { apiDownloadPost } = await import("./client");
    const pending = apiDownloadPost("/industry-chain/export-pdf", { a: 1 }, "r.pdf");
    const assertion = expect(pending).rejects.toBeInstanceOf(ApiTimeoutError);

    await vi.advanceTimersByTimeAsync(API_TIMEOUTS.LONG_RUNNING);
    await assertion;
    expect(fetchSignal?.aborted).toBe(true);
  });

  it("honours an explicit timeoutMs for downloads", async () => {
    vi.stubGlobal("fetch", vi.fn((_url, init) => new Promise<Response>((_resolve, reject) => {
      (init?.signal as AbortSignal | undefined)?.addEventListener(
        "abort",
        () => reject(new DOMException("aborted", "AbortError")),
        { once: true },
      );
    })));
    const { apiDownload } = await import("./client");
    const pending = apiDownload("/x", "f.pdf", undefined, { timeoutMs: 1000 });
    const assertion = expect(pending).rejects.toBeInstanceOf(ApiTimeoutError);

    await vi.advanceTimersByTimeAsync(1000);
    await assertion;
  });

  it("still propagates a caller abort on downloads", async () => {
    let fetchSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url, init) => {
      fetchSignal = init?.signal as AbortSignal;
      return new Promise<Response>((_resolve, reject) => {
        fetchSignal?.addEventListener(
          "abort",
          () => reject(new DOMException("aborted", "AbortError")),
          { once: true },
        );
      });
    }));
    const { apiDownload } = await import("./client");
    const caller = new AbortController();
    const pending = apiDownload("/x", "f.pdf", undefined, { signal: caller.signal });
    const assertion = expect(pending).rejects.toBeDefined();

    caller.abort();
    await assertion;
    expect(fetchSignal?.aborted).toBe(true);
  });
});
