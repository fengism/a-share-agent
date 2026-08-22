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
}));

vi.mock("../client", async () => {
  const actual = await vi.importActual<typeof import("../client")>("../client");
  return { ...actual, apiGet: vi.fn() };
});

vi.mock("../../hooks/useAStockTradingSession", () => ({
  useAStockTradingSession: () => mocks.isTradingSession,
}));

function getRefetchInterval(queryClient: QueryClient, queryKey: readonly unknown[]) {
  const options = queryClient.getQueryCache().find({ queryKey })?.options as {
    refetchInterval?: unknown;
  } | undefined;
  return options?.refetchInterval;
}

describe("account realtime query polling", () => {
  beforeEach(() => {
    mocks.isTradingSession = true;
    vi.mocked(apiGet).mockReset().mockResolvedValue({});
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
    expect(getRefetchInterval(queryClient, queryKeys.portfolio)).toBe(30_000);
    expect(getRefetchInterval(queryClient, queryKeys.watchlist)).toBe(30_000);

    mocks.isTradingSession = false;
    rerender();

    expect(getRefetchInterval(queryClient, queryKeys.portfolio)).toBe(false);
    expect(getRefetchInterval(queryClient, queryKeys.watchlist)).toBe(false);
    unmount();
    queryClient.clear();
  });
});
