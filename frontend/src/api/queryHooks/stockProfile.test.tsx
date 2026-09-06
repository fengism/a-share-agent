import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { openApiGet } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { useStockBusinessIntro, useStockChipDistribution, useStockInfo } from "./stock";

vi.mock("../openapiClient", async () => {
  const actual = await vi.importActual<typeof import("../openapiClient")>("../openapiClient");
  return { ...actual, openApiGet: vi.fn() };
});

function createQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function createWrapper(queryClient: QueryClient) {
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("stock profile queries", () => {
  afterEach(() => vi.mocked(openApiGet).mockReset());

  it("loads stock info with the reference cache policy", async () => {
    vi.mocked(openApiGet).mockResolvedValue({ code: "600519", name: "贵州茅台" });
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useStockInfo("600519"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/stock/{code}/info", {
      path: { code: "600519" },
    });
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.stock.info("600519"),
    })?.options as { staleTime?: unknown } | undefined;
    expect(options?.staleTime).toBe(QUERY_CACHE_POLICIES.reference.staleMs);
    queryClient.clear();
  });

  it("loads persisted business intro with the reference cache policy", async () => {
    vi.mocked(openApiGet).mockResolvedValue({
      code: "600519",
      source: "ths",
      items: { 主营业务: "白酒产品的生产与销售" },
    });
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useStockBusinessIntro("600519"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/stock/{code}/business-intro", {
      path: { code: "600519" },
    });
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.stock.businessIntro("600519"),
    })?.options as { staleTime?: unknown } | undefined;
    expect(options?.staleTime).toBe(QUERY_CACHE_POLICIES.reference.staleMs);
    queryClient.clear();
  });

  it("loads chip distribution with the market cache policy", async () => {
    vi.mocked(openApiGet).mockResolvedValue({
      code: "600519",
      as_of_date: "2026-09-02",
      histogram: [],
    });
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useStockChipDistribution("600519"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/stock/{code}/chip-distribution", {
      path: { code: "600519" },
    });
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.stock.chipDistribution("600519"),
    })?.options as { staleTime?: unknown } | undefined;
    expect(options?.staleTime).toBe(QUERY_CACHE_POLICIES.marketTenMinutes.staleMs);
    queryClient.clear();
  });

  it("does not request profile data without a stock code", () => {
    const queryClient = createQueryClient();
    renderHook(() => {
      useStockInfo("");
      useStockBusinessIntro("");
      useStockChipDistribution("");
    }, { wrapper: createWrapper(queryClient) });

    expect(openApiGet).not.toHaveBeenCalled();
    queryClient.clear();
  });
});
