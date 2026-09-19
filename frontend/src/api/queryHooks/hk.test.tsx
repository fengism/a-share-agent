import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QUERY_CACHE_POLICIES } from "../cachePolicies";
import { openApiGet } from "../openapiClient";
import { queryKeys } from "../queryKeys";
import { useHKIndices, useHKStockSearch } from "./hk";

const mocks = vi.hoisted(() => ({
  isHKTradingSession: true,
}));

vi.mock("../../hooks/useHKStockTradingSession", () => ({
  useHKStockTradingSession: () => mocks.isHKTradingSession,
}));

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

describe("Hong Kong stock search query", () => {
  afterEach(() => vi.mocked(openApiGet).mockReset());

  it("passes the cancellation signal and applies the search cache policy", async () => {
    vi.mocked(openApiGet).mockResolvedValue({ items: [] });
    const queryClient = createQueryClient();
    const { result } = renderHook(() => useHKStockSearch("腾讯"), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(openApiGet).toHaveBeenCalledWith("/api/hk/stocks/search", {
      query: { q: "腾讯", limit: 8 },
      options: {
        timeoutMs: expect.any(Number),
        signal: expect.any(AbortSignal),
      },
    });
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.hk.stockSearch("腾讯"),
    })?.options as { staleTime?: unknown; gcTime?: unknown } | undefined;
    expect(options?.staleTime).toBe(QUERY_CACHE_POLICIES.hkStockSearch.staleMs);
    expect(options?.gcTime).toBe(QUERY_CACHE_POLICIES.hkStockSearch.gcMs);
    queryClient.clear();
  });

  it("aborts an obsolete request when the search term changes", async () => {
    let firstSignal: AbortSignal | undefined;
    vi.mocked(openApiGet).mockImplementation((_path, args) => {
      const query = args?.query as { q?: string } | undefined;
      const signal = args?.options?.signal;
      if (query?.q === "腾讯") {
        firstSignal = signal;
        return new Promise(() => undefined);
      }
      return Promise.resolve({ items: [] });
    });
    const queryClient = createQueryClient();
    const { result, rerender } = renderHook(
      ({ query }) => useHKStockSearch(query),
      { initialProps: { query: "腾讯" }, wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => expect(firstSignal).toBeDefined());
    rerender({ query: "阿里" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(firstSignal?.aborted).toBe(true);
    queryClient.clear();
  });
});

describe("Hong Kong indices query polling", () => {
  it("polls every 30 seconds in session and disables it off session", async () => {
    mocks.isHKTradingSession = true;
    vi.mocked(openApiGet).mockResolvedValue([]);
    const queryClient = createQueryClient();
    const { result, rerender, unmount } = renderHook(() => useHKIndices(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const getInterval = () => {
      const options = queryClient.getQueryCache().find({
        queryKey: queryKeys.hk.indices,
      })?.options as { refetchInterval?: unknown } | undefined;
      return options?.refetchInterval;
    };

    expect(getInterval()).toBe(30_000);

    mocks.isHKTradingSession = false;
    rerender();
    expect(getInterval()).toBe(false);

    unmount();
    queryClient.clear();
  });
});
