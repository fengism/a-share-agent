import { describe, expect, it } from "vitest";
import { ApiError, ApiTimeoutError } from "./client";
import { shouldRetryQuery } from "./queryClient";

describe("shouldRetryQuery", () => {
  it("retries a network error only once", () => {
    expect(shouldRetryQuery(0, new TypeError("network failed"))).toBe(true);
    expect(shouldRetryQuery(1, new TypeError("network failed"))).toBe(false);
  });

  it("retries server errors but not client errors", () => {
    expect(shouldRetryQuery(0, new ApiError(503, "/market", "unavailable"))).toBe(true);
    expect(shouldRetryQuery(0, new ApiError(404, "/analysis", "missing"))).toBe(false);
  });

  it("does not retry timeouts or aborted requests", () => {
    expect(shouldRetryQuery(0, new ApiTimeoutError(1000))).toBe(false);
    expect(shouldRetryQuery(0, new DOMException("aborted", "AbortError"))).toBe(false);
  });
});
