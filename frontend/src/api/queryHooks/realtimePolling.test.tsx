import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../client";
import { queryKeys } from "../queryKeys";
import { usePortfolio } from "./portfolio";
import { useWatchlist } from "./watchlist";

const mocks = vi.hoisted(() => ({
  isTradingSession: true,
  isHKSession: false,
}));

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn() };
});

vi.mock("../../hooks/useAStockTradingSession", () => ({
  useAStockTradingSession: () => mocks.isTradingSession,
}));

vi.mock("../../hooks/useHKStockTradingSession", () => ({
  useHKStockTradingSession: () => mocks.isHKSession,
}));

const hkItem = {
  id: 1,
  stock_code: "00700",
  market: "hk" as const,
  stock_name: "腾讯控股",
  note: "",
  created_at: "2026-08-20T10:00:00",
  current_price: 380,
  change_pct: 1.2,
  open_price: 376,
  high_price: 382,
  low_price: 375,
  previous_close: 375.5,
  volume: 1_000_000,
  amount: 380_000_000,
  turnover_pct: 0.1,
  pe_ttm: 18,
  market_cap: 3_600_000_000_000,
  quote_source: "tencent",
  concepts: [],
  alerts: [],
};

/** Resolve the (possibly function-form) refetchInterval against the cached query. */
function resolveRefetchInterval(queryClient: QueryClient, queryKey: readonly unknown[]) {
  const query = queryClient.getQueryCache().find({ queryKey });
  const interval = (query?.options as { refetchInterval?: unknown } | undefined)?.refetchInterval;
  if (typeof interval === "function") {
    return (interval as (q: unknown) => unknown)(query);
  }
  return interval;
}

describe("account realtime query polling", () => {
  beforeEach(() => {
    mocks.isTradingSession = true;
    mocks.isHKSession = false;
    vi.mocked(apiGet).mockReset().mockImplementation(async (path: string) => {
      if (path === "/watchlist") {
        return { items: [hkItem], source: "tencent", quoted_at: "2026-08-30T10:30:00" } as never;
      }
      return {} as never;
    });
  });

  it("retains thirty-second polling in-session and disables it off-session", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result, rerender, unmount } = renderHook(() => ({
      portfolio: usePortfolio(),
      watchlist: useWatchlist(),
    }), { wrapper });

    await waitFor(() => expect(result.current.portfolio.isSuccess && result.current.watchlist.isSuccess).toBe(true));
    expect(resolveRefetchInterval(queryClient, queryKeys.portfolio)).toBe(30_000);
    expect(resolveRefetchInterval(queryClient, queryKeys.watchlist)).toBe(30_000);

    mocks.isTradingSession = false;
    rerender();

    expect(resolveRefetchInterval(queryClient, queryKeys.portfolio)).toBe(false);
    expect(resolveRefetchInterval(queryClient, queryKeys.watchlist)).toBe(false);
    unmount();
    queryClient.clear();
  });

  it("keeps polling a Hong Kong watchlist during the HK-only tail session", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result, rerender, unmount } = renderHook(() => useWatchlist(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // A 股收盘、港股仍在交易：含港股自选应继续刷新
    mocks.isTradingSession = false;
    mocks.isHKSession = true;
    rerender();
    expect(resolveRefetchInterval(queryClient, queryKeys.watchlist)).toBe(30_000);
    unmount();
    queryClient.clear();
  });

  it("does not poll a pure A-share watchlist during the HK-only tail session", async () => {
    vi.mocked(apiGet).mockImplementation(async () => ({
      items: [{ ...hkItem, id: 2, stock_code: "600519", market: "cn", stock_name: "贵州茅台" }],
      source: "tencent",
      quoted_at: "2026-08-30T10:30:00",
    }) as never);
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    const { result, rerender, unmount } = renderHook(() => useWatchlist(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    mocks.isTradingSession = false;
    mocks.isHKSession = true;
    rerender();
    expect(resolveRefetchInterval(queryClient, queryKeys.watchlist)).toBe(false);
    unmount();
    queryClient.clear();
  });
});
