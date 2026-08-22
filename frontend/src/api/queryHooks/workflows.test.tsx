import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { openApiGet } from "../openapiClient";
import { useAnalysisHistorySnapshot } from "./workflows";

vi.mock("../openapiClient", async () => {
  const actual = await vi.importActual<typeof import("../openapiClient")>("../openapiClient");
  return { ...actual, openApiGet: vi.fn() };
});

describe("analysis history snapshot query", () => {
  afterEach(() => vi.mocked(openApiGet).mockReset());

  it("loads the selected dated analysis", async () => {
    vi.mocked(openApiGet).mockResolvedValue({
      stock_code: "600519",
      stock_name: "贵州茅台",
      analysis_date: "20260807",
    } as never);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );

    const { result } = renderHook(
      () => useAnalysisHistorySnapshot("600519", "20260807"),
      { wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/analysis/{code}/history/{date}", {
      path: { code: "600519", date: "20260807" },
    });
    queryClient.clear();
  });
});
