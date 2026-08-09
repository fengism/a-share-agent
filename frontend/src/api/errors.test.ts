import { describe, expect, it } from "vitest";
import { parseApiError } from "./errors";

describe("parseApiError", () => {
  it("parses the generated error response contract", () => {
    expect(parseApiError({
      code: "auth.invalid_credentials",
      message: "用户名或密码错误",
      request_id: "request-1",
      error_id: "error-1",
    }, "fallback")).toEqual({
      code: "auth.invalid_credentials",
      message: "用户名或密码错误",
      requestId: "request-1",
      errorId: "error-1",
    });
  });

  it("keeps compatibility with legacy detail responses", () => {
    expect(parseApiError({ detail: "legacy" }, "fallback").message).toBe("legacy");
    expect(parseApiError(null, "fallback").message).toBe("fallback");
  });
});
