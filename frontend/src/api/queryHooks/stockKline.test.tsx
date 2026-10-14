import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, API_TIMEOUTS } from "../client";
import { queryKeys } from "../queryKeys";
import { useKlineData } from "./stock";


const mocks = vi.hoisted(() => ({
  isTradingSession: true,
}));

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn() };
});

vi.mock("../../hooks/useAStockTradingSession", () => ({
  useAStockTradingSession: () => mocks.isTradingSession,
}));

type KlineQueryOptions = { staleTime?: unknown; refetchInterval?: unknown } | undefined;

function renderKline(options?: Parameters<typeof useKlineData>[5]): KlineQueryOptions {
  vi.mocked(apiGet).mockResolvedValue({ code: "600519", period: "daily", items: [] });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  renderHook(() => useKlineData("600519", "daily", "qfq", true, undefined, options), { wrapper });
  return queryClient.getQueryCache().getAll()[0]?.options as KlineQueryOptions;
}

describe("useKlineData live refresh", () => {
  beforeEach(() => {
    mocks.isTradingSession = true;
  });

  afterEach(() => vi.mocked(apiGet).mockReset());

  it("polls the in-progress daily bar during the trading session when liveRefresh is on", () => {
    const options = renderKline({ liveRefresh: true });
    expect(options?.staleTime).toBe(30_000);
    expect(options?.refetchInterval).toBe(60_000);
  });

  it("does not poll once the session is closed", () => {
    mocks.isTradingSession = false;
    const options = renderKline({ liveRefresh: true });
    expect(options?.refetchInterval).not.toBe(60_000);
    expect(options?.staleTime).toBe(600_000);
  });

  it("does not poll by default (historical/backtest views)", () => {
    const options = renderKline();
    expect(options?.refetchInterval).not.toBe(60_000);
    expect(options?.staleTime).toBe(600_000);
  });

  it("does not poll when an explicit historical end date is set", () => {
    vi.mocked(apiGet).mockResolvedValue({ code: "600519", period: "daily", items: [] });
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const wrapper = ({ children }: PropsWithChildren) => (
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    );
    renderHook(
      () => useKlineData("600519", "daily", "qfq", true, { startDate: "20260102", endDate: "20260105" }, { liveRefresh: true }),
      { wrapper },
    );
    const options = queryClient.getQueryCache().find({
      queryKey: queryKeys.stock.kline("600519", "daily", "qfq", "20260102", "20260105"),
    })?.options as { refetchInterval?: unknown } | undefined;
    expect(options?.refetchInterval).not.toBe(60_000);
  });

  it("requests kline data with external timeout budget", () => {
    renderKline();
    expect(apiGet).toHaveBeenCalledWith(
      "/stock/600519/kline",
      expect.objectContaining({ period: "daily", adjust: "qfq" }),
      { timeoutMs: API_TIMEOUTS.EXTERNAL },
    );
  });
});
