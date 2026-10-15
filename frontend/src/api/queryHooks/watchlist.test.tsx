import type { PropsWithChildren } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { apiDelete, apiPost } from "../client";
import { useAddWatchlistAlert, useAddWatchlistItem, useDeleteWatchlistItem } from "./watchlist";

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiPost: vi.fn(), apiDelete: vi.fn() };
});

function createWrapper() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return ({ children }: PropsWithChildren) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("watchlist mutation market inference", () => {
  afterEach(() => {
    vi.mocked(apiPost).mockReset();
    vi.mocked(apiDelete).mockReset();
  });

  it("infers the HK market for a 5-digit code when adding", async () => {
    vi.mocked(apiPost).mockResolvedValue({} as never);
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper: createWrapper() });

    await result.current.mutateAsync({ stock_code: "00700", note: "" });

    expect(apiPost).toHaveBeenCalledWith("/watchlist", { stock_code: "00700", note: "", market: "hk" });
  });

  it("keeps the A-share market for a 6-digit code", async () => {
    vi.mocked(apiPost).mockResolvedValue({} as never);
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper: createWrapper() });

    await result.current.mutateAsync({ stock_code: "600519", note: "" });

    expect(apiPost).toHaveBeenCalledWith("/watchlist", { stock_code: "600519", note: "", market: "cn" });
  });

  it("honours an explicit market over the inferred one", async () => {
    vi.mocked(apiPost).mockResolvedValue({} as never);
    const { result } = renderHook(() => useAddWatchlistItem(), { wrapper: createWrapper() });

    await result.current.mutateAsync({ stock_code: "00700", market: "cn", note: "" });

    expect(apiPost).toHaveBeenCalledWith("/watchlist", { stock_code: "00700", market: "cn", note: "" });
  });

  it("deletes an HK code with the market query flag", async () => {
    vi.mocked(apiDelete).mockResolvedValue(true as never);
    const { result } = renderHook(() => useDeleteWatchlistItem(), { wrapper: createWrapper() });

    await result.current.mutateAsync("00700");

    expect(apiDelete).toHaveBeenCalledWith("/watchlist/00700?market=hk");
  });

  it("deletes an A-share code without a market flag", async () => {
    vi.mocked(apiDelete).mockResolvedValue(true as never);
    const { result } = renderHook(() => useDeleteWatchlistItem(), { wrapper: createWrapper() });

    await result.current.mutateAsync("600519");

    expect(apiDelete).toHaveBeenCalledWith("/watchlist/600519");
  });

  it("infers the HK market for alerts", async () => {
    vi.mocked(apiPost).mockResolvedValue({} as never);
    const { result } = renderHook(() => useAddWatchlistAlert(), { wrapper: createWrapper() });

    await result.current.mutateAsync({
      stockCode: "00700",
      request: { condition: "price_above", threshold: 100 },
    });

    expect(apiPost).toHaveBeenCalledWith("/watchlist/00700/alerts", {
      condition: "price_above",
      threshold: 100,
      market: "hk",
    });
  });
});
