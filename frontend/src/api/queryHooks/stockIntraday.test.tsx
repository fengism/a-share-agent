import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { apiGet } from "../client";
import { queryKeys } from "../queryKeys";
import { useStockIntraday } from "./stock";

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn() };
});
vi.mock("../../hooks/useAStockTradingSession", () => ({ useAStockTradingSession: () => true }));

describe("useStockIntraday", () => {
  it("uses aggregate initial data and refreshes every thirty seconds", async () => {
    vi.mocked(apiGet).mockResolvedValue({ code: "600519", source: "sina", prev_close: 10, items: [] });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const initialData = { code: "600519", source: "aggregate", prev_close: 10, items: [] };

    const { result } = renderHook(() => useStockIntraday("600519", initialData), { wrapper });

    expect(result.current.data?.source).toBe("aggregate");
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.stock.intraday("600519"),
    })?.options as { staleTime?: unknown; refetchInterval?: unknown } | undefined;
    expect(options?.staleTime).toBe(30_000);
    expect(options?.refetchInterval).toBe(30_000);
    await result.current.refetch();
    await waitFor(() => expect(apiGet).toHaveBeenCalledWith("/stock/600519/intraday", undefined, undefined));
    queryClient.clear();
  });
});
