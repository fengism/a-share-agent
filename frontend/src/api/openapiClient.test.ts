import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./client", () => ({
  apiDelete: vi.fn(),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  apiPut: vi.fn(),
}));

import { apiGet } from "./client";
import { asApiModel, openApiGet, openApiPost } from "./openapiClient";

function assertRequiredArgumentsAtCompileTime() {
  // @ts-expect-error Generated path parameters are required.
  openApiGet("/api/industry-chain/{name}/latest");
  // @ts-expect-error Generated required query parameters are required.
  openApiGet("/api/market/index-kline");
  // @ts-expect-error Generated request bodies are required.
  openApiPost("/api/push");
  // @ts-expect-error Generated required body fields cannot be omitted.
  openApiPost("/api/push", { body: {} });
  // @ts-expect-error API model adaptation cannot invent required response fields.
  asApiModel<{ required: string }>()({});
}
void assertRequiredArgumentsAtCompileTime;

describe("openapiClient", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("interpolates and encodes generated path parameters", async () => {
    vi.mocked(apiGet).mockResolvedValue({ archive_id: "a", saved_at: "now" });

    await openApiGet("/api/industry-chain/{name}/latest", {
      path: { name: "AI 芯片" },
      options: { timeoutMs: 1000 },
    });

    expect(apiGet).toHaveBeenCalledWith(
      "/industry-chain/AI%20%E8%8A%AF%E7%89%87/latest",
      undefined,
      { timeoutMs: 1000 },
    );
  });

  it("forwards generated query parameters", async () => {
    vi.mocked(apiGet).mockResolvedValue([]);

    await openApiGet("/api/stock/{code}/kline", {
      path: { code: "600519" },
      query: { period: "daily", adjust: "qfq" },
    });

    expect(apiGet).toHaveBeenCalledWith(
      "/stock/600519/kline",
      { period: "daily", adjust: "qfq" },
      undefined,
    );
  });
});
